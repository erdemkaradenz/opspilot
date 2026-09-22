# seed.py
"""
İdempotent tohumlama scripti.
Varsayılan organizasyonu oluşturur (eğer yoksa).
Konteyner ayağa kalkarken `alembic upgrade head`'den sonra çalıştırılır.
"""
import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Organization  # Kendi model yoluna göre düzelt

load_dotenv()

# Veritabanı URL'sini al, yoksa direkt çöksün (Fail-fast prensibi)
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("[HATA] DATABASE_URL çevre değişkeni bulunamadı!")
    sys.exit(1)

# Eğer lokalden gelen URL 'asyncpg' içermiyorsa güvenli bir şekilde ekle
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Bağlantı motorunu oluştur
engine = create_async_engine(DB_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

DEFAULT_ORG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

async def seed():
    try:
        async with AsyncSessionLocal() as session:
            existing = await session.get(Organization, DEFAULT_ORG_ID)
            if existing:
                print(f"[SEED] Varsayılan organizasyon zaten mevcut: {existing.name} ({existing.id})")
                return

            default_org = Organization(
                id=DEFAULT_ORG_ID,
                name="Default Organization",
                plan="free",
            )
            session.add(default_org)
            await session.commit()
            print(f"[SEED] Varsayılan organizasyon başarıyla oluşturuldu: {default_org.name}")
            
    except Exception as e:
        print(f"[SEED HATA] Tohumlama işlemi sırasında kritik bir hata oluştu: {str(e)}")
        sys.exit(1) # Konteynerin hatalı durumda çalışmasını engelle (Crash-loop'a sok)
        
    finally:
        # MİMARIN KİLİDİ: Asenkron motoru temiz bir şekilde kapat
        await engine.dispose()
        print("[SEED] Veritabanı bağlantısı güvenli bir şekilde kapatıldı.")

if __name__ == "__main__":
    asyncio.run(seed())