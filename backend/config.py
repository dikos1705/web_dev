from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    db_host: str = 'database'
    db_port: int = 5432
    db_name: str = 'aeron'
    db_user: str = 'aeron'
    db_password: SecretStr
    admin_api_key: SecretStr = Field(min_length=24)
    booking_secret: SecretStr = Field(min_length=32)
    seed_demo: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
