# db/session.py
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

load_dotenv()

# Senkron URL'yi async driver'a çeviriyoruz (asyncpg kullanacak)
ASYNC_DB_URL = os.environ["DATABASE_URL"].replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(ASYNC_DB_URL, pool_size=5, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    """FastAPI Dependency: Her request için bir DB oturumu açar, işlem bitince kapatır."""
    async with AsyncSessionLocal() as session:
        yield session
