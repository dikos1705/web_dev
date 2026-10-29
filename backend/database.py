from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()
engine = create_engine(
    URL.create('postgresql+psycopg', username=settings.db_user,
               password=settings.db_password.get_secret_value(),
               host=settings.db_host, port=settings.db_port, database=settings.db_name),
    pool_pre_ping=True, pool_size=10, max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session
