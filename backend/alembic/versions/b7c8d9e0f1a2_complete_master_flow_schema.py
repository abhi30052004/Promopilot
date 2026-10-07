"""Complete master-flow media and publish metadata.

Revision ID: b7c8d9e0f1a2
Revises: 6e48922ca894
Create Date: 2026-10-07 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "6e48922ca894"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "generated_media",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_publish_logs_content_id", "publish_logs", ["content_id"], unique=False)
    op.create_foreign_key(
        "fk_publish_logs_content_id_content_items",
        "publish_logs",
        "content_items",
        ["content_id"],
        ["id"],
    )
    op.execute("UPDATE publish_logs SET content_id=content_item_id WHERE content_id IS NULL")


def downgrade() -> None:
    op.drop_constraint(
        "fk_publish_logs_content_id_content_items", "publish_logs", type_="foreignkey"
    )
    op.drop_index("ix_publish_logs_content_id", table_name="publish_logs")
    op.drop_column("generated_media", "updated_at")
