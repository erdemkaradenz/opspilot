"""fix_severity_enum_and_server_defaults

Revision ID: b2f4a7c8d901
Revises: a1c8e1f4d256
Create Date: 2026-09-19 22:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f4a7c8d901"
down_revision: str | Sequence[str] | None = "a1c8e1f4d256"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. incidentseverity ENUM tipini oluştur (yoksa)
    # NOT: Bu tip daha önce elle oluşturulduysa hata vermez
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE incidentseverity AS ENUM ('SEV_1', 'SEV_2', 'SEV_3'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    # 2. severity kolonunu VARCHAR(50) → incidentseverity ENUM'a dönüştür
    # Mevcut verileri ENUM name'lerine cast et
    op.execute(
        "ALTER TABLE incidents "
        "ALTER COLUMN severity TYPE incidentseverity "
        "USING severity::incidentseverity;"
    )

    # 3. server_default ekle — artık DB seviyesinde de default çalışacak
    op.alter_column("organizations", "created_at", server_default=sa.text("now()"))
    op.alter_column("incidents", "started_at", server_default=sa.text("now()"))


def downgrade() -> None:
    """Downgrade schema."""

    # server_default'ları kaldır
    op.alter_column("incidents", "started_at", server_default=None)
    op.alter_column("organizations", "created_at", server_default=None)

    # severity'yi tekrar VARCHAR'a çevir
    op.execute(
        "ALTER TABLE incidents "
        "ALTER COLUMN severity TYPE VARCHAR(50) "
        "USING severity::text;"
    )

    # ENUM tipini sil
    op.execute("DROP TYPE IF EXISTS incidentseverity;")
