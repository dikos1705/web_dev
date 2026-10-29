"""Dayboard REST API. PostgreSQL stores every task."""
import os
from pathlib import Path

import psycopg
from flask import Flask, jsonify, request, send_file, url_for
from werkzeug.exceptions import HTTPException

from database import connect, initialize_database
from validation import parse_task

ROOT = Path(__file__).parent


def task_json(task):
    return {**task, 'created_at': task['created_at'].isoformat().replace('+00:00', 'Z')}


def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
    initialize_database()

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(ValueError)
    def validation_error(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(psycopg.Error)
    def database_error(error):
        app.logger.error('Database request failed (%s)', type(error).__name__)
        return jsonify(error='Database temporarily unavailable'), 503

    @app.get('/')
    def home():
        return send_file(ROOT / 'index.html')

    @app.get('/api/openapi.json')
    def specification():
        return send_file(ROOT / 'docs/openapi.json', mimetype='application/json')

    @app.get('/health')
    def health():
        with connect() as connection:
            connection.execute('SELECT 1').fetchone()
        return jsonify(status='ok', database='connected')

    @app.get('/api/info')
    def info():
        return jsonify(name='Dayboard', version='1.0.0',
                       message=os.environ.get('APP_MESSAGE', 'Make room for good work.'),
                       port=int(os.environ.get('PORT', '8000')))

    @app.get('/api/tasks')
    def list_tasks():
        clauses, values = [], []
        unknown = set(request.args) - {'completed', 'priority', 'q'}
        if unknown:
            raise ValueError('Unknown query parameter: ' + ', '.join(sorted(unknown)))
        if 'completed' in request.args:
            completed = request.args['completed']
            if completed not in ('true', 'false'):
                raise ValueError('completed query parameter must be true or false')
            clauses.append('completed = %s')
            values.append(completed == 'true')
        if 'priority' in request.args:
            priority = request.args['priority']
            if priority not in ('low', 'medium', 'high'):
                raise ValueError('Priority must be low, medium or high')
            clauses.append('priority = %s')
            values.append(priority)
        if 'q' in request.args:
            query = request.args['q'].strip()
            if not 1 <= len(query) <= 120:
                raise ValueError('Search must contain 1 to 120 characters')
            clauses.append('strpos(lower(title), lower(%s)) > 0')
            values.append(query)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        with connect() as connection:
            tasks = connection.execute('SELECT * FROM tasks' + where + ' ORDER BY completed, id DESC', values).fetchall()
        return jsonify(tasks=[task_json(task) for task in tasks])

    @app.get('/api/tasks/<int:task_id>')
    def get_task(task_id):
        if not 1 <= task_id <= 2147483647:
            return jsonify(error='Task not found'), 404
        with connect() as connection:
            task = connection.execute('SELECT * FROM tasks WHERE id = %s', (task_id,)).fetchone()
        if task is None:
            return jsonify(error='Task not found'), 404
        return jsonify(task_json(task))

    @app.post('/api/tasks')
    def add_task():
        data = parse_task(request.get_json(), mode='create')
        with connect() as connection:
            task = connection.execute(
                'INSERT INTO tasks (title, priority, completed) VALUES (%s, %s, %s) RETURNING *',
                (data['title'], data['priority'], data['completed'])).fetchone()
        response = jsonify(task_json(task))
        response.status_code = 201
        response.headers['Location'] = url_for('get_task', task_id=task['id'])
        return response

    @app.route('/api/tasks/<int:task_id>', methods=['PUT', 'PATCH'])
    def update_task(task_id):
        data = parse_task(request.get_json(), mode='replace' if request.method == 'PUT' else 'patch')
        if not 1 <= task_id <= 2147483647:
            return jsonify(error='Task not found'), 404
        with connect() as connection:
            task = connection.execute('''UPDATE tasks SET
                title = COALESCE(%s, title), priority = COALESCE(%s, priority),
                completed = COALESCE(%s, completed) WHERE id = %s RETURNING *''',
                (data.get('title'), data.get('priority'), data.get('completed'), task_id)).fetchone()
        if task is None:
            return jsonify(error='Task not found'), 404
        return jsonify(task_json(task))

    @app.delete('/api/tasks/<int:task_id>')
    def delete_task(task_id):
        if not 1 <= task_id <= 2147483647:
            return jsonify(error='Task not found'), 404
        with connect() as connection:
            removed = connection.execute('DELETE FROM tasks WHERE id = %s RETURNING id', (task_id,)).fetchone()
        if removed is None:
            return jsonify(error='Task not found'), 404
        return '', 204

    @app.get('/api/stats')
    def stats():
        with connect() as connection:
            result = connection.execute('''SELECT count(*) AS total,
                count(*) FILTER (WHERE completed) AS completed,
                count(*) FILTER (WHERE NOT completed) AS remaining,
                count(*) FILTER (WHERE NOT completed AND priority = 'high') AS urgent
                FROM tasks''').fetchone()
        return jsonify(result)

    return app
