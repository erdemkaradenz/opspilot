# schemas/telemetry.py
from pydantic import BaseModel, Field
from typing import Dict, Any
from datetime import datetime
from uuid import UUID

class TelemetryEvent(BaseModel):
    tenant_id: UUID = Field(..., description="Müşterinin (Organizasyon) benzersiz kimliği")
    service_id: UUID = Field(..., description="Hatanın fırlatıldığı servisin kimliği")
    type: str = Field(..., description="Olayın tipi, örn: ERROR, METRIC, ANOMALY")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Olayın gerçekleşme zamanı")
    fingerprint: str = Field(..., description="Olayı tekilleştirmek için benzersiz parmak izi (örn: redis_timeout_v1)")
    payload: Dict[str, Any] = Field(..., description="Logun veya metriğin asıl içeriği")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "service_id": "123e4567-e89b-12d3-a456-426614174001",
                "type": "ERROR",
                "fingerprint": "db_connection_failed",
                "payload": {"error": "Connection refused", "port": 5432}
            }
        }