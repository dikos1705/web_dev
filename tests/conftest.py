import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.database import Base, database_url, get_session
from backend.main import app
from backend.seed import seed_database


@pytest.fixture
def db_engine():
    # Every test gets a separate PostgreSQL schema; public/user tables are never dropped.
    if "DB_PASSWORD" not in os.environ:
        pytest.fail("Set DB_HOST/PORT/NAME/USER/PASSWORD for a running PostgreSQL test database")
    admin = create_engine(database_url(), connect_args={"connect_timeout": 5})
    schema = "test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        database_url(),
        connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5},
    )
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session, session.begin():
            seed_database(session)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def client(db_engine):
    def override_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    # Not entering TestClient avoids startup seeding the configured non-test schema.
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
