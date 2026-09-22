# api/analysis.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from aiokafka import AIOKafkaProducer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json

from api.ingestion import get_kafka_producer
from db.session import get_db
from models import Incident, IncidentEvidence

router = APIRouter()

@router.post("/incidents/{incident_id}/analyze", status_code=202)
async def trigger_ai_analysis(
    incident_id: uuid.UUID,
    force: bool = False,
    producer: AIOKafkaProducer = Depends(get_kafka_producer),
    db: AsyncSession = Depends(get_db)
):
    """
    AI analizini başlatır ve HTTP isteğini bloklamadan anında 202 Accepted döner.
    
    - Incident DB'de yoksa 404 döner.
    - Evidence yoksa 400 döner (AI'a gönderecek veri yok).
    - Zaten analiz edilmişse 409 döner (force=true ile geçersiz kılınabilir).
    """
    # 1. Incident var mı kontrol et
    incident = await db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident bulunamadı: {incident_id}")
    
    # 2. Evidence var mı kontrol et
    evidence_count_stmt = select(func.count()).select_from(IncidentEvidence).where(
        IncidentEvidence.incident_id == incident_id
    )
    evidence_count = (await db.execute(evidence_count_stmt)).scalar()
    
    if evidence_count == 0:
        has_evidence = False
    else:
        has_evidence = True
    
    # 3. Zaten analiz edilmiş mi kontrol et
    if incident.ai_rca_summary and not force:
        raise HTTPException(
            status_code=409,
            detail="Bu incident zaten analiz edilmiş. "
                   "Tekrar analiz etmek için force=true parametresini kullanın."
        )
    
    # 4. Tüm kontroller geçti — Kafka'ya gönder
    job_id = str(uuid.uuid4())
    
    task_payload = {
        "job_id": job_id,
        "incident_id": str(incident_id)
    }
    
    # Gerçek sistemlerde tracing (Correlation ID) buraya da enjekte edilir.
    await producer.send_and_wait("ai_analysis_tasks", json.dumps(task_payload).encode("utf-8"))
    
    message = "AI analysis started in the background."
    if not has_evidence:
        message = "⚠️ Evidence bulunamadı. Kural bazlı bildirim gönderilecek (AI analizi atlanacak)."
    
    return JSONResponse(
        status_code=202,
        content={
            "status": "Accepted",
            "message": message,
            "job_id": job_id,
            "incident_id": str(incident_id),
            "evidence_count": evidence_count
        }
    )