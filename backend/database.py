import os
from collections.abc import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> URL:
    # URL.create correctly escapes special characters in the password.
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("DB_USER", "bounty"),
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "bounty"),
    )


def make_engine():
    return create_engine(database_url(), pool_pre_ping=True, connect_args={"connect_timeout": 5})


def get_session() -> Generator[Session, None, None]:
    from backend.main import app

    with app.state.session_factory() as session:
        yield session


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
