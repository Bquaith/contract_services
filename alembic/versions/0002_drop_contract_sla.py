"""drop sla from contracts

Revision ID: 0002_drop_contract_sla
Revises: 0001_initial
Create Date: 2026-02-17 10:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_drop_contract_sla"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'contracts' AND column_name = 'sla'
              ) THEN
                ALTER TABLE contracts DROP COLUMN sla;
              END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'contracts' AND column_name = 'sla'
              ) THEN
                ALTER TABLE contracts ADD COLUMN sla JSONB NULL;
              END IF;
            END $$;
            """
        )
    )
