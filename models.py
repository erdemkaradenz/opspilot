import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import JSON, Text
from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum as SQLEnum
from schemas.incident import IncidentSeverity

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=sa.func.now())

class TenantAwareModel(Base):
    """
    Kritik: Tüm multi-tenant modeller bu sınıftan türeyecek.
    Eğer bir tabloya org_id koymayı unutursan bu sınıf seni korur.
    """
    __abstract__ = True
    
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("organizations.id", ondelete="CASCADE"), 
        nullable=False
    )

class User(TenantAwareModel):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False) # Admin, Engineer, Viewer
    
    __table_args__ = (
        Index('ix_users_org_id', 'org_id'), # 10 bin kullanıcıda veritabanının kilitlenmemesi için index!
    )

class Service(TenantAwareModel):
    __tablename__ = "services"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    
    __table_args__ = (
        Index('ix_services_org_id', 'org_id'),
    )

class Incident(TenantAwareModel):
    __tablename__ = "incidents"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(
        SQLEnum(IncidentSeverity), 
        default=IncidentSeverity.SEV_3, 
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="open") 
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=sa.func.now())
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # --- AI VE RAG KOLONLARI BURAYA GELECEK ---
    ai_rca_summary: Mapped[str] = mapped_column(Text, nullable=True) 
    
    # DİKKAT: Gemini text-embedding-004 kullandığımız için boyut 768!
    # Eğer buraya 1536 yazarsan veya boş bırakırsan DB tokatlar.
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)

    __table_args__ = (
        Index('ix_incidents_tenant_fingerprint', 'org_id', 'fingerprint'),
    )

class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(100)) # Olayın kaynağı (örn: TELEMETRY)
    content: Mapped[dict] = mapped_column(JSON, nullable=False) # Logun asıl gövdesi