from models import Base
from db.session import engine # Kendi veritabanı engine'ini buraya import et

print("Veritabanı tabloları oluşturuluyor...")
Base.metadata.create_all(bind=engine)
print("İşlem tamamlandı.")