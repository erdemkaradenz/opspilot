import asyncio
import json
import os
from dotenv import load_dotenv
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from models import Incident, IncidentEvidence
from schemas.incident import IncidentSeverity

from opentelemetry import trace
from opentelemetry.propagate import extract
from core.tracing import setup_tracing

tracer = setup_tracing("opspilot-incident-worker")

load_dotenv()
KAFKA_BROKER = os.environ["KAFKA_BROKER_URL"]
# Senkron URL'yi asenkron URL'ye çeviriyoruz (Production'da çok hayat kurtarır)
ASYNC_DB_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_DB_URL, pool_size=5, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def process_event(event_data: dict):
    tenant_id = event_data.get("tenant_id")
    fingerprint = event_data.get("fingerprint")
    
    async with AsyncSessionLocal() as session:
        async with session.begin(): # Transaction başlat
            # Açık (open) bir incident var mı diye bak (Deduplication)
            stmt = select(Incident).where(
                Incident.org_id == tenant_id,
                Incident.fingerprint == fingerprint,
                Incident.status == "open"
            )
            result = await session.execute(stmt)
            incident = result.scalars().first()

            if not incident:
                # Yeni Incident Yarat
                incident = Incident(
                    org_id=tenant_id,
                    fingerprint=fingerprint,
                    severity=IncidentSeverity.SEV_2 if event_data.get("type") == "ERROR" else IncidentSeverity.SEV_3
                )
                session.add(incident)
                await session.flush() # ID'yi almak için DB'ye fırlat (henüz commit değil)
                print(f"[+] YENI OLAY YARATILDI: {incident.id}")
            else:
                print(f"[*] MEVCUT OLAY GÜNCELLENDİ (Deduplicated): {incident.id}")

            # Her halükarda gelen veriyi kanıt (evidence) olarak ekle
            evidence = IncidentEvidence(
                incident_id=incident.id,
                source_type=event_data.get("type", "TELEMETRY"),
                content=event_data.get("payload", {})
            )
            session.add(evidence)
        # Context manager bitince otomatik COMMIT atılır.

async def consume_telemetry():
    consumer = AIOKafkaConsumer(
        "telemetry_events",
        bootstrap_servers=KAFKA_BROKER,
        group_id="incident-engine-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False
    )
    
    await consumer.start()
    print("[WORKER] Kafka Consumer başladı. Mesajlar bekleniyor...")
    
    try:
        async for msg in consumer:
            # Kafka header'larını normal sözlüğe (dict) çevir
            headers = {k: v.decode("utf-8") for k, v in (msg.headers or [])}
            
            # Üst sistemden (API'den) gelen Trace ID'yi çıkar ve devam et
            context = extract(headers)
            
            with tracer.start_as_current_span("process_kafka_message", context=context):
                try:
                    event_data = json.loads(msg.value.decode("utf-8"))
                    await process_event(event_data)
                    await consumer.commit()
                except Exception as e:
                    print(f"[WORKER ERROR] Mesaj işlenemedi: {e}")
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume_telemetry())