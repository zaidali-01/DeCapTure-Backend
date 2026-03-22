from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str 
    JWT_ALGORITHM: str 
    ACCESS_TOKEN_EXPIRE_MINUTES: int 
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()