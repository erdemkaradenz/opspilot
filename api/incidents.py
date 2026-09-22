# api/incidents.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models import Incident
from schemas.incident import IncidentCreate

router = APIRouter()


@router.post("/incidents", status_code=201)
async def create_manual_incident(
    payload: IncidentCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Sisteme manuel olarak veya 3. parti bir adaptörden (örn: PagerDuty)
    Olay (Incident) yaratılmasını sağlar.
    """
    # 1. API Kapısı (Pydantic Enum) payload'u zaten doğruladı. Buraya inebildiyse veri %100 temizdir.

    # 2. Veritabanına kaydet
    new_incident = Incident(
        fingerprint=payload.fingerprint,
        severity=payload.severity,
        org_id=uuid.UUID(payload.org_id),
    )
    db.add(new_incident)
    await db.commit()
    await db.refresh(new_incident)

    print(
        f"[API] Yeni Olay Yaratıldı! ID: {new_incident.id} | Seviye: {payload.severity}"
    )

    return {
        "status": "success",
        "message": "Incident manually created",
        "incident_id": str(new_incident.id),
        "severity": payload.severity,
    }
