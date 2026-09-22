# schemas/incident.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
import enum

class IncidentSeverity(str, enum.Enum):
    SEV_1 = "SEV-1"
    SEV_2 = "SEV-2"
    SEV_3 = "SEV-3"

class IncidentCreate(BaseModel):
    fingerprint: str
    severity: IncidentSeverity = Field(default=IncidentSeverity.SEV_3)
    org_id: str

    model_config = ConfigDict(from_attributes=True)