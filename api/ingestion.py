from typing import Annotated

from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from opentelemetry.propagate import inject

from schemas.telemetry import TelemetryEvent

router = APIRouter()
kafka_producer: AIOKafkaProducer = None


async def get_kafka_producer():
    return kafka_producer


async def custom_rate_limiter(request: Request):
    """
    Saf Redis INCR tabanlı, sıfır maliyetli Rate Limiter.
    Client IP'sine göre saniyede maksimum 5 isteğe izin verir.
    """
    redis = request.app.state.redis
    client_ip = request.client.host
    key = f"rate_limit:ip:{client_ip}"

    # Atomic sayaç artırımı (Redis çok hızlıdır, DB'yi yormaz)
    requests = await redis.incr(key)

    # Eğer anahtar yeni oluşturulduysa, 1 saniye sonra yok olması için (TTL) süre tanımla
    if requests == 1:
        await redis.expire(key, 10)

    if requests > 5:
        raise HTTPException(
            status_code=429, detail="Too Many Requests - OpsPilot Shield"
        )


@router.post(
    "/telemetry/events",
    status_code=202,
    dependencies=[
        Depends(custom_rate_limiter)
    ],  # Kendi yazdığımız koruma kalkanı devrede
)
async def ingest_telemetry(
    event: TelemetryEvent,
    producer: Annotated[AIOKafkaProducer, Depends(get_kafka_producer)],
):
    message = event.model_dump_json().encode("utf-8")

    # ingest_telemetry fonksiyonunun içine, producer.send_and_wait kodundan hemen önce şunu ekle:
    headers = {}
    # Mevcut Trace ID'yi Kafka headers'ına enjekte et
    inject(headers)

    # Byte'a çevirirken dictionary'yi Kafka'nın kabul edeceği List[Tuple[str, bytes]] formatına sokuyoruz
    kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

    # producer kısmını güncelle
    await producer.send_and_wait(
        "telemetry_events", value=message, headers=kafka_headers
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "Accepted",
            "message": "Event queued for processing",
            "fingerprint": event.fingerprint,
        },
    )
