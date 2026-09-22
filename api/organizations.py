# api/organizations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from schemas.organization import OrganizationCreate, OrganizationResponse
from models import Organization

router = APIRouter()


@router.post("/organizations", status_code=201, response_model=OrganizationResponse)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Yeni bir organizasyon oluşturur."""
    new_org = Organization(
        name=payload.name,
        plan=payload.plan,
    )
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)

    print(f"[API] Yeni Organizasyon Oluşturuldu! ID: {new_org.id} | Ad: {new_org.name}")
    return new_org


@router.get("/organizations", response_model=list[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db)
):
    """Tüm organizasyonları listeler."""
    stmt = select(Organization)
    result = await db.execute(stmt)
    return result.scalars().all()
