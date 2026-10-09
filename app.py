"""Homework 2: persistent task board with PostgreSQL and Flask."""
import os
import time
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import HTTPException


def connect():
    return psycopg.connect(host=os.environ['DB_HOST'], port=int(os.environ.get('DB_PORT', '5432')),
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
        connect_timeout=3, row_factory=dict_row)


def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
    for attempt in range(30):
        try:
            with connect() as connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    title VARCHAR(120) NOT NULL CHECK (length(trim(title)) > 0),
                    priority VARCHAR(10) NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            break
        except psycopg.OperationalError:
            if attempt == 29:
                raise RuntimeError('Database did not become ready') from None
            time.sleep(1)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(psycopg.Error)
    def database_error(error):
        app.logger.error('Database request failed (%s)', type(error).__name__)
        return jsonify(error='Database temporarily unavailable'), 503

    @app.get('/')
    def home():
        return send_file(Path(__file__).with_name('index.html'))

    @app.get('/health')
    def health():
        with connect() as connection:
            connection.execute('SELECT 1').fetchone()
        return jsonify(status='ok', database='connected')

    @app.get('/api/info')
    def info():
        return jsonify(message=os.environ.get('APP_MESSAGE', 'Make room for good work.'),
                       port=int(os.environ.get('PORT', '8000')))

    @app.get('/api/tasks')
    def list_tasks():
        with connect() as connection:
            tasks = connection.execute('SELECT * FROM tasks ORDER BY completed, id DESC').fetchall()
        return jsonify(tasks=tasks)

    @app.post('/api/tasks')
    def add_task():
        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify(error='Send a JSON object'), 400
        title, priority = data.get('title'), data.get('priority', 'medium')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            return jsonify(error='Title must contain 1 to 120 characters'), 400
        if not isinstance(priority, str) or priority not in ('low', 'medium', 'high'):
            return jsonify(error='Priority must be low, medium or high'), 400
        with connect() as connection:
            task = connection.execute('INSERT INTO tasks (title, priority) VALUES (%s, %s) RETURNING *',
                                      (title.strip(), priority)).fetchone()
        return jsonify(task), 201

    @app.patch('/api/tasks/<int:task_id>')
    def update_task(task_id):
        data = request.get_json()
        if not isinstance(data, dict) or type(data.get('completed')) is not bool:
            return jsonify(error='completed must be a JSON boolean'), 400
        with connect() as connection:
            task = connection.execute('UPDATE tasks SET completed = %s WHERE id = %s RETURNING *',
                                      (data['completed'], task_id)).fetchone()
        if task is None:
            return jsonify(error='Task not found'), 404
        return jsonify(task)

    @app.delete('/api/tasks/<int:task_id>')
    def delete_task(task_id):
        with connect() as connection:
            removed = connection.execute('DELETE FROM tasks WHERE id = %s RETURNING id', (task_id,)).fetchone()
        if removed is None:
            return jsonify(error='Task not found'), 404
        return '', 204

    @app.get('/api/stats')
    def stats():
        with connect() as connection:
            result = connection.execute("""SELECT count(*) AS total,
                count(*) FILTER (WHERE completed) AS completed,
                count(*) FILTER (WHERE NOT completed) AS remaining,
                count(*) FILTER (WHERE NOT completed AND priority = 'high') AS urgent
                FROM tasks""").fetchone()
        return jsonify(result)

    return app
