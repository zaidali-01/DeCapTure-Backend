from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


def _build_engine():
    if not settings.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in your environment or .env file."
        )

    try:
        return create_async_engine(
            settings.DATABASE_URL,
            echo=True,
            future=True,
        )
    except ModuleNotFoundError as exc:
        if exc.name == "asyncpg":
            raise RuntimeError(
                "The PostgreSQL async driver 'asyncpg' is missing. "
                "Install project dependencies with `pip install -r requirements.txt`."
            ) from exc
        raise


engine = _build_engine()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
