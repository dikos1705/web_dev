"""Connection settings and idempotent schema initialization."""
import os
import time

import psycopg
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(
        host=os.environ['DB_HOST'], port=int(os.environ.get('DB_PORT', '5432')),
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'], connect_timeout=3, row_factory=dict_row,
    )


def initialize_database():
    for attempt in range(30):
        try:
            with connect() as connection:
                connection.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    title VARCHAR(120) NOT NULL CHECK (length(trim(title)) > 0),
                    priority VARCHAR(10) NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            return
        except psycopg.OperationalError:
            if attempt == 29:
                raise RuntimeError('Database did not become ready') from None
            time.sleep(1)
