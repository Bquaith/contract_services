"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-09 22:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("namespace", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum("table", "topic", name="entity_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owners", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "target_layer",
            sa.Enum("raw", "curated", "audit", name="target_layer", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "archived", name="contract_status", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("active_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace", "name", name="uq_contract_namespace_name"),
    )
    op.create_index(op.f("ix_contracts_name"), "contracts", ["name"], unique=False)
    op.create_index(op.f("ix_contracts_namespace"), "contracts", ["namespace"], unique=False)

    op.create_table(
        "contract_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "stable", "deprecated", name="version_status", native_enum=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "compatibility_mode",
            sa.Enum(
                "backward",
                "forward",
                "full",
                "none",
                name="compatibility_mode",
                native_enum=False,
            ),
            nullable=False,
            server_default="backward",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False, server_default="system"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", "version", name="uq_contract_version"),
    )
    op.create_index(op.f("ix_contract_versions_contract_id"), "contract_versions", ["contract_id"], unique=False)

    op.create_table(
        "compatibility_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_version", sa.String(length=64), nullable=False),
        sa.Column("candidate_version", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            sa.Enum(
                "backward",
                "forward",
                "full",
                "none",
                name="compatibility_mode_check",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "verdict",
            sa.Enum("ok", "warn", "fail", name="compatibility_verdict", native_enum=False),
            nullable=False,
        ),
        sa.Column("violations_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("diff_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False, server_default="system"),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_compatibility_checks_contract_id"),
        "compatibility_checks",
        ["contract_id"],
        unique=False,
    )

    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "target",
            sa.Enum("schema", "compatibility", name="validation_target", native_enum=False),
            nullable=False,
        ),
        sa.Column("input_ref", sa.String(length=255), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum("ok", "fail", name="validation_verdict", native_enum=False),
            nullable=False,
        ),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("validation_runs")
    op.drop_index(op.f("ix_compatibility_checks_contract_id"), table_name="compatibility_checks")
    op.drop_table("compatibility_checks")
    op.drop_index(op.f("ix_contract_versions_contract_id"), table_name="contract_versions")
    op.drop_table("contract_versions")
    op.drop_index(op.f("ix_contracts_namespace"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_name"), table_name="contracts")
    op.drop_table("contracts")
