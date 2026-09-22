# api/incidents.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from db.session import get_db
from schemas.incident import IncidentCreate
from models import Incident

router = APIRouter()

@router.post("/incidents", status_code=201)
async def create_manual_incident(
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db)
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
    
    print(f"[API] Yeni Olay Yaratıldı! ID: {new_incident.id} | Seviye: {payload.severity}")
    
    return {
        "status": "success", 
        "message": "Incident manually created", 
        "incident_id": str(new_incident.id),
        "severity": payload.severity
    }