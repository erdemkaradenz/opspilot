# schemas/ai.py
from pydantic import BaseModel, Field


class RootCauseAnalysis(BaseModel):
    kök_neden: str = Field(
        description="Teknik kök nedenin (Root Cause) 1-2 cümlelik kesin açıklaması."
    )
    çözüm_adımları: list[str] = Field(
        description="Nöbetçi mühendisin uygulaması gereken adım adım çözüm talimatları."
    )
    güven_skoru: float = Field(
        description="AI'ın bu analize duyduğu güven. 0.0 ile 1.0 arası."
    )
    referans_olay_idleri: list[str] = Field(
        description="Bu çözüme varılırken RAG ile veritabanından çekilen geçmiş benzer olayların (Incident) UUID'leri."
    )
