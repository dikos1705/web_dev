from collections.abc import AsyncIterator

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()
engine = create_async_engine(
    URL.create('postgresql+psycopg', username=settings.db_user,
               password=settings.db_password.get_secret_value(),
               host=settings.db_host, port=settings.db_port, database=settings.db_name),
    pool_pre_ping=True, pool_size=10, max_overflow=10,
)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
