"""Master flow schema: property_images, generated_media, new columns

Revision ID: a1b2c3d4e5f6
Revises: edb33c9a01f5
Create Date: 2026-10-07 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'edb33c9a01f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JsonVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    # ── generated_media (must come before property_images & content_items reference it) ──
    op.create_table(
        'generated_media',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('property_id', sa.Integer(), sa.ForeignKey('properties.id'), nullable=True, index=True),
        sa.Column('content_id', sa.Integer(), sa.ForeignKey('content_items.id'), nullable=True, index=True),
        sa.Column('media_type', sa.String(), nullable=False),          # IMAGE | VIDEO
        sa.Column('provider', sa.String(), nullable=True),             # SCRAPED | OPENAI | FFMPEG | PILLOW
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('storage_url', sa.Text(), nullable=True),
        sa.Column('thumbnail_url', sa.Text(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('generation_status', sa.String(), nullable=False, server_default='PENDING'),  # PENDING|GENERATING|COMPLETED|FAILED
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('is_ai_generated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_generated_media_id', 'generated_media', ['id'])

    # ── property_images ──
    op.create_table(
        'property_images',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('property_id', sa.Integer(), sa.ForeignKey('properties.id'), nullable=False, index=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),  # PENDING|VALID|BROKEN
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('media_id', sa.Integer(), sa.ForeignKey('generated_media.id'), nullable=True),
        sa.Column('is_ai_generated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('checked_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_property_images_id', 'property_images', ['id'])

    # ── extend properties ──
    op.add_column('properties', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('properties', sa.Column('title', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('price', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('category', sa.String(), nullable=True))
    op.add_column('properties', sa.Column('approval_status', sa.String(), nullable=False, server_default='PENDING'))
    op.add_column('properties', sa.Column('approved_at', sa.DateTime(), nullable=True))
    op.add_column('properties', sa.Column('rejected_at', sa.DateTime(), nullable=True))
    op.add_column('properties', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.add_column('properties', sa.Column('media_status', sa.String(), nullable=False, server_default='PENDING'))
    op.add_column('properties', sa.Column('content_generation_status', sa.String(), nullable=False, server_default='NONE'))
    op.add_column('properties', sa.Column('scraped_at', sa.DateTime(), nullable=True))
    # Backfill: approval_status=PENDING, scraped_at=created_at
    op.execute("UPDATE properties SET approval_status='PENDING', scraped_at=created_at WHERE approval_status IS NULL OR approval_status=''")

    # ── extend content_items ──
    op.add_column('content_items', sa.Column('variant_number', sa.Integer(), nullable=True))
    op.add_column('content_items', sa.Column('angle', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('title', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('generation_date', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('media_id', sa.Integer(), sa.ForeignKey('generated_media.id'), nullable=True))
    op.add_column('content_items', sa.Column('approval_status', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('publish_status', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.add_column('content_items', sa.Column('story_hook', sa.Text(), nullable=True))
    op.add_column('content_items', sa.Column('story_message', sa.Text(), nullable=True))
    op.add_column('content_items', sa.Column('visual_concept', sa.Text(), nullable=True))
    op.add_column('content_items', sa.Column('generation_status', sa.String(), nullable=True, server_default='PENDING'))
    op.add_column('content_items', sa.Column('error', sa.Text(), nullable=True))

    # Migrate legacy status -> approval_status + publish_status
    op.execute("""
        UPDATE content_items SET
            approval_status = CASE status
                WHEN 'draft' THEN 'PENDING'
                WHEN 'pending_approval' THEN 'PENDING'
                WHEN 'approved' THEN 'APPROVED'
                WHEN 'scheduled' THEN 'APPROVED'
                WHEN 'published' THEN 'APPROVED'
                WHEN 'failed' THEN 'APPROVED'
                WHEN 'rejected' THEN 'REJECTED'
                ELSE 'PENDING'
            END,
            publish_status = CASE status
                WHEN 'draft' THEN 'DRAFT'
                WHEN 'pending_approval' THEN 'DRAFT'
                WHEN 'approved' THEN 'DRAFT'
                WHEN 'scheduled' THEN 'SCHEDULED'
                WHEN 'published' THEN 'PUBLISHED'
                WHEN 'failed' THEN 'FAILED'
                WHEN 'rejected' THEN 'DRAFT'
                ELSE 'DRAFT'
            END
        WHERE approval_status IS NULL
    """)

    # ── extend publish_logs ──
    op.add_column('publish_logs', sa.Column('content_id', sa.Integer(), nullable=True))
    op.add_column('publish_logs', sa.Column('published_at', sa.DateTime(), nullable=True))
    op.add_column('publish_logs', sa.Column('external_post_id', sa.String(), nullable=True))

    # ── automation_logs ──
    op.create_table(
        'automation_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('action', sa.String(), nullable=True, index=True),   # PROPERTY_AUTO_APPROVED, etc.
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('mode', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    )
    op.create_index('ix_automation_logs_id', 'automation_logs', ['id'])


def downgrade() -> None:
    op.drop_table('automation_logs')
    op.drop_column('publish_logs', 'external_post_id')
    op.drop_column('publish_logs', 'published_at')
    op.drop_column('publish_logs', 'content_id')
    op.drop_column('content_items', 'error')
    op.drop_column('content_items', 'generation_status')
    op.drop_column('content_items', 'visual_concept')
    op.drop_column('content_items', 'story_message')
    op.drop_column('content_items', 'story_hook')
    op.drop_column('content_items', 'rejection_reason')
    op.drop_column('content_items', 'publish_status')
    op.drop_column('content_items', 'approval_status')
    op.drop_column('content_items', 'media_id')
    op.drop_column('content_items', 'generation_date')
    op.drop_column('content_items', 'title')
    op.drop_column('content_items', 'angle')
    op.drop_column('content_items', 'variant_number')
    op.drop_column('properties', 'scraped_at')
    op.drop_column('properties', 'content_generation_status')
    op.drop_column('properties', 'media_status')
    op.drop_column('properties', 'rejection_reason')
    op.drop_column('properties', 'rejected_at')
    op.drop_column('properties', 'approved_at')
    op.drop_column('properties', 'approval_status')
    op.drop_column('properties', 'category')
    op.drop_column('properties', 'price')
    op.drop_column('properties', 'title')
    op.drop_column('properties', 'source_url')
    op.drop_table('property_images')
    op.drop_table('generated_media')
