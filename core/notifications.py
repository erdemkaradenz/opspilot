import httpx
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

load_dotenv()

N8N_WEBHOOK_URL = os.environ["N8N_WEBHOOK_URL"]

class NotificationDeliveryError(Exception):
    pass

# Eğer istek başarısız olursa 2 saniye, 4 saniye, 8 saniye diyerek en fazla 5 kez tekrar dener.
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
async def send_to_n8n_with_retry(payload: dict):
    """n8n webhook'una olay verilerini güvenilir şekilde fırlatır."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(N8N_WEBHOOK_URL, json=payload)
            response.raise_for_status() # 4xx veya 5xx dönerse hata fırlat ve retry'ı tetikle
            print(f"[NOTIFICATION] n8n'e başarıyla iletildi. Durum: {response.status_code}")
        except httpx.HTTPStatusError as e:
            print(f"[NOTIFICATION ERROR] n8n reddetti: {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            print(f"[NOTIFICATION ERROR] n8n'e ulaşılamıyor: {e}")
            raise