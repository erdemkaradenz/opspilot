# workers/ai_worker.py
import asyncio
import json
import os
from dotenv import load_dotenv
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, update
from openai import AsyncOpenAI
from models import Incident, IncidentEvidence
from schemas.ai import RootCauseAnalysis
from core.notifications import send_to_n8n_with_retry

load_dotenv()
KAFKA_BROKER = os.environ["KAFKA_BROKER_URL"]
ASYNC_DB_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_DB_URL, pool_size=5, max_overflow=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# OpenAI SDK'sını Google Gemini sunucularına yönlendiriyoruz
client = AsyncOpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

async def generate_embedding(text: str) -> list[float]:
    """Metni vektöre çevirir (Token maliyeti yaratır, dikkatli kullan!)."""
    response = await client.embeddings.create(
        input=text[:8000], # Maliyet ve limit koruması
        model="gemini-embedding-001" # Google'ın 768 boyutlu modeli
    )
    return response.data[0].embedding

async def process_ai_analysis(task_data: dict):
    incident_id = task_data["incident_id"]
    job_id = task_data["job_id"]
    
    print(f"[AI WORKER] Analiz başladı. Job ID: {job_id} | Incident: {incident_id}")
    
    async with AsyncSessionLocal() as session:
        # 1. Hatanın içeriğini ve kanıtlarını (Evidence) veritabanından çek
        incident = await session.get(Incident, incident_id)
        if not incident:
            print("[AI WORKER] Incident bulunamadı!")
            return

        stmt = select(IncidentEvidence).where(IncidentEvidence.incident_id == incident_id)
        evidences = (await session.execute(stmt)).scalars().all()
        
        # ── EVIDENCE GUARD ──────────────────────────────────────────────
        # Evidence yoksa AI analizini ATLA. LLM'e log/metrik kanıtı olmadan
        # kök neden sormak token israfı ve halüsinasyona yol açar.
        # Bunun yerine kural bazlı (rule-based) basit bildirim gönder.
        if not evidences:
            print(f"[AI WORKER] Evidence bulunamadı! AI analizi atlanıyor. Kural bazlı bildirim gönderiliyor.")
            
            incident.ai_rca_summary = json.dumps({
                "durum": "Analiz atlandı: Evidence (kanıt) bulunamadı",
                "açıklama": "Bu olay için henüz log veya metrik kanıtı yok. AI analizi kanıt toplandıktan sonra tekrar tetiklenebilir."
            }, ensure_ascii=False)
            await session.commit()
            
            # Kural bazlı bildirim — AI çıkarımı olmadan sadece olay bilgisi
            rule_based_payload = {
                "incident_id": str(incident_id),
                "severity": incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity),
                "ai_rca": f"⚠️ Kanıt bekleniyor — Fingerprint: {incident.fingerprint}",
                "confidence": 0.0
            }
            asyncio.create_task(send_to_n8n_with_retry(rule_based_payload))
            return
        # ── EVIDENCE GUARD SONU ─────────────────────────────────────────
        
        # Olayın metin havuzunu oluştur
        incident_text = " ".join([json.dumps(ev.content) for ev in evidences])
        
        # 2. Vektör Oluştur (Embedding)
        print("[AI WORKER] Vektör embedding üretiliyor...")
        current_embedding = await generate_embedding(incident_text)
        
        # 3. RAG: pgvector ile "Buna Benzeyen" geçmiş çözülmüş olayları bul (Cosine Similarity)
        # Cosine distance: <-> operatörü pgvector'de kullanılır.
        # DİKKAT: org_id filtresi ile multi-tenant izolasyonu sağlanıyor!
        print("[AI WORKER] Geçmiş olaylar taranıyor (Vector Search)...")
        rag_stmt = select(Incident).where(
            Incident.org_id == incident.org_id,  # Multi-tenant izolasyonu!
            Incident.embedding != None,
            Incident.id != incident_id # Kendini bulma
        ).order_by(
            Incident.embedding.cosine_distance(current_embedding)
        ).limit(3)
        
        similar_incidents = (await session.execute(rag_stmt)).scalars().all()
        
        # 4. LLM Prompt'unu İnşa Et (Prompt Engineering)
        context_text = "\n".join([
            f"- Eski Olay ({sim.id}): {sim.ai_rca_summary}" for sim in similar_incidents
        ])
        
        system_prompt = (
            "Sen kıdemli bir AWS/Sistem Mimarı ve SRE (Site Reliability Engineer) yapay zekasısın. "
            "Sana bir hata logu (Incident) ve geçmişte yaşanmış benzer hataların listesi (Context) verilecek. "
            "SADECE bu verilere dayanarak hatanın kök nedenini bul ve çözüm adımlarını yaz. "
            "Kesinlikle yapılandırılmış JSON döneceksin. Edebi laf kalabalığı yapma."
        )
        
        user_prompt = f"GÜNCEL HATA KANITLARI:\n{incident_text}\n\nGEÇMİŞ BENZER OLAYLAR KANITLARI (RAG):\n{context_text if similar_incidents else 'Geçmiş veri yok.'}"
        
        # 5. LLM Çıkarımı (Structured Outputs - Garantili JSON)
        print("[AI WORKER] Google Gemini API'sine (gemini-3.6-flash) gönderiliyor...")
        completion = await client.beta.chat.completions.parse(
            model="gemini-3.6-flash", # Hızlı ve JSON uyumlu model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=RootCauseAnalysis, 
        )
        
        # Modelin döndüğü %100 tip güvenli Pydantic objesi
        ai_response: RootCauseAnalysis = completion.choices[0].message.parsed
        
        # 6. Veritabanını Güncelle
        incident.ai_rca_summary = ai_response.model_dump_json()
        # Modeli 768 boyuta zorluyoruz (Maliyet Optimizasyonu!)
        incident.embedding = current_embedding[:768] 
        await session.commit()
        
        print(f"[AI WORKER BAŞARILI] Incident {incident_id} güncellendi.")
        # 7. Otomasyon ve Bildirim Katmanını Tetikle
        alert_payload = {
            "incident_id": str(incident_id),
            "severity": incident.severity.value if hasattr(incident.severity, 'value') else str(incident.severity),
            "ai_rca": ai_response.kök_neden,
            "confidence": ai_response.güven_skoru
        }
        
        # Bunu arkaplanda asenkron fırlatıyoruz, Worker'ın ana döngüsünü tıkamasın
        asyncio.create_task(send_to_n8n_with_retry(alert_payload))

async def consume_ai_tasks():
    consumer = AIOKafkaConsumer(
        "ai_analysis_tasks",
        bootstrap_servers=KAFKA_BROKER,
        group_id="ai-engine-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False
    )
    
    await consumer.start()
    print("[AI WORKER] Kafka AI Consumer başladı. Görevler bekleniyor...")
    
    try:
        async for msg in consumer:
            task_data = json.loads(msg.value.decode("utf-8"))
            try:
                await process_ai_analysis(task_data)
                await consumer.commit()
            except Exception as e:
                print(f"[AI WORKER ERROR] Görev işlenemedi: {e}")
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume_ai_tasks())