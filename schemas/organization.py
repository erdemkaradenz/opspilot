# schemas/organization.py
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Organizasyon adı")
    plan: str = Field(default="free", description="Abonelik planı (free, pro, enterprise)")


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    plan: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
