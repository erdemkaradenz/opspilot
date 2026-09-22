import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()
# Alembic'in ve sistemin kullandığı GERÇEK veritabanı adresi
ASYNC_DB_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(ASYNC_DB_URL)

async def fix():
    async with engine.begin() as conn:
        # Uzantıyı her ihtimale karşı aktifleştir
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Asıl veritabanındaki sorunlu kolonları acımasızca yok et
        await conn.execute(text("ALTER TABLE incidents DROP COLUMN IF EXISTS embedding;"))
        await conn.execute(text("ALTER TABLE incidents DROP COLUMN IF EXISTS ai_rca_summary;"))
        print("[+] OpsPilot asıl veritabanı temizlendi! Kolonlar yok edildi.")

asyncio.run(fix())