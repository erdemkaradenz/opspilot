# schemas/incident.py
import enum

from pydantic import BaseModel, ConfigDict, Field


class IncidentSeverity(str, enum.Enum):
    SEV_1 = "SEV-1"
    SEV_2 = "SEV-2"
    SEV_3 = "SEV-3"


class IncidentCreate(BaseModel):
    fingerprint: str
    severity: IncidentSeverity = Field(default=IncidentSeverity.SEV_3)
    org_id: str

    model_config = ConfigDict(from_attributes=True)
