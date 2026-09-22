# main.py
import os
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaProducer
from dotenv import load_dotenv
from fastapi import FastAPI

# from fastapi_limiter import FastAPILimiter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from redis import asyncio as aioredis

import api.analysis as analysis_api
import api.incidents as incidents_api
import api.ingestion as ingestion_api
import api.organizations as organizations_api
from core.tracing import setup_tracing

load_dotenv()

REDIS_URL = os.environ["REDIS_URL"]
KAFKA_BROKER = os.environ["KAFKA_BROKER_URL"]

# Tracing'i başlat
tracer = setup_tracing("opspilot-ingestion-gateway")
SQLAlchemyInstrumentor().instrument()  # Veritabanı sorgularının sürelerini otomatik ölçer


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Redis bağlantısı (Hatalara Dayanıklı)
    try:
        app.state.redis = aioredis.from_url(
            REDIS_URL, encoding="utf8", decode_responses=True
        )
        print("✅ Redis aktif ve state'e eklendi.")
    except Exception as e:
        print(f"⚠️ Redis bağlantı hatası (Atlanıyor): {e}")
        app.state.redis = None

    # Kafka Producer (Hatalara Dayanıklı)
    try:
        ingestion_api.kafka_producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
        await ingestion_api.kafka_producer.start()
        print("✅ Kafka Producer aktif.")
    except Exception as e:
        print(f"⚠️ Kafka bağlantı hatası (Atlanıyor): {e}")
        ingestion_api.kafka_producer = None

    yield

    # Kapanışta kaynakları sızdırmadan (memory leak) temizle
    if hasattr(app.state, 'redis') and app.state.redis:
        await app.state.redis.close()
        
    if getattr(ingestion_api, 'kafka_producer', None):
        await ingestion_api.kafka_producer.stop()
        
    print("Bağlantılar güvenli bir şekilde kapatıldı.")


app = FastAPI(title="OpsPilot Ingestion Gateway", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

# Rotaları uygulamaya dahil et
app.include_router(ingestion_api.router)
app.include_router(analysis_api.router)
app.include_router(incidents_api.router)
app.include_router(organizations_api.router)
