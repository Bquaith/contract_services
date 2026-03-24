"""add compatibility tracking fields

Revision ID: 0003_compat_fields
Revises: 0002_drop_contract_sla
Create Date: 2026-02-20 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_compat_fields"
down_revision = "0002_drop_contract_sla"
branch_labels = None
depends_on = None


def upgrade() -> None:
    version_bump_enum = sa.Enum(
        "major",
        "minor",
        "patch",
        name="version_bump_type",
        native_enum=False,
    )
    version_bump_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "compatibility_checks",
        sa.Column(
            "version_bump",
            version_bump_enum,
            nullable=True,
        ),
    )
    op.add_column(
        "compatibility_checks",
        sa.Column(
            "backward_compatible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "compatibility_checks",
        sa.Column(
            "forward_compatible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "compatibility_checks",
        sa.Column(
            "full_compatible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "compatibility_checks",
        sa.Column(
            "policy_passed",
            sa.Boolean(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("compatibility_checks", "policy_passed")
    op.drop_column("compatibility_checks", "full_compatible")
    op.drop_column("compatibility_checks", "forward_compatible")
    op.drop_column("compatibility_checks", "backward_compatible")
    op.drop_column("compatibility_checks", "version_bump")

    sa.Enum(
        "major",
        "minor",
        "patch",
        name="version_bump_type",
        native_enum=False,
    ).drop(op.get_bind(), checkfirst=True)
