"""End-to-end spec: article context, multi-platform content, per-platform publish logs.

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-10-07 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONV = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    # properties: full scraped context + reproducible snapshot
    op.add_column("properties", sa.Column("content", sa.Text()))
    op.add_column("properties", sa.Column("summary", sa.Text()))
    op.add_column("properties", sa.Column("tags", JSONV))
    op.add_column("properties", sa.Column("language", sa.String()))
    op.add_column("properties", sa.Column("source_snapshot", JSONV))
    op.add_column("properties", sa.Column("source_published_at", sa.DateTime()))

    op.add_column("generated_media", sa.Column("file_name", sa.String()))

    # content_items: one item, many platforms
    op.add_column("content_items", sa.Column("platform_targets", JSONV))
    op.add_column("content_items", sa.Column("contact_email", sa.String()))
    op.add_column("content_items", sa.Column("source_snapshot", JSONV))
    op.add_column("content_items", sa.Column("generation_mode", sa.String()))
    op.add_column(
        "content_items",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.drop_constraint("uq_content_items_v2", "content_items", type_="unique")
    op.create_unique_constraint(
        "uq_content_items_v3",
        "content_items",
        ["property_id", "generation_date", "kind", "variant_number", "language"],
    )

    # publish_logs: one row per (content, platform)
    op.add_column("publish_logs", sa.Column("scheduled_at", sa.DateTime()))
    op.add_column(
        "publish_logs",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "publish_logs",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_unique_constraint(
        "uq_publish_logs_content_platform", "publish_logs", ["content_id", "platform"]
    )

    op.add_column("automation_logs", sa.Column("language", sa.String()))
    op.add_column("automation_logs", sa.Column("platform", sa.String()))


def downgrade() -> None:
    op.drop_column("automation_logs", "platform")
    op.drop_column("automation_logs", "language")
    op.drop_constraint("uq_publish_logs_content_platform", "publish_logs", type_="unique")
    op.drop_column("publish_logs", "updated_at")
    op.drop_column("publish_logs", "is_demo")
    op.drop_column("publish_logs", "scheduled_at")
    op.drop_constraint("uq_content_items_v3", "content_items", type_="unique")
    op.create_unique_constraint(
        "uq_content_items_v2",
        "content_items",
        ["property_id", "generation_date", "kind", "variant_number", "platform", "language"],
    )
    for col in ("updated_at", "generation_mode", "source_snapshot", "contact_email", "platform_targets"):
        op.drop_column("content_items", col)
    op.drop_column("generated_media", "file_name")
    for col in ("source_published_at", "source_snapshot", "language", "tags", "summary", "content"):
        op.drop_column("properties", col)
