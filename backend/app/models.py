from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Float, UniqueConstraint, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base

# JSON columns defined as JSON().with_variant(JSONB, "postgresql")
JsonVariant = JSON().with_variant(JSONB, "postgresql")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    type = Column(String)
    description = Column(Text)
    amenities = Column(JsonVariant)
    location = Column(String)
    url = Column(String)
    images = Column(JsonVariant)          # legacy list of local paths – kept for compat
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # New columns
    source_url = Column(Text)
    title = Column(String)
    price = Column(String)
    category = Column(String)
    approval_status = Column(String, default='PENDING', nullable=False)  # PENDING|APPROVED|REJECTED
    approved_at = Column(DateTime)
    rejected_at = Column(DateTime)
    rejection_reason = Column(Text)
    media_status = Column(String, default='PENDING', nullable=False)         # PENDING|PROCESSING|SUCCESS|FAILED
    content_generation_status = Column(String, default='NONE', nullable=False)  # NONE|PENDING|PROCESSING|SUCCESS|FAILED
    scraped_at = Column(DateTime)

    # Spec additions: full scraped context + reproducible snapshot for AI generation.
    content = Column(Text)                 # full article/property text
    summary = Column(Text)
    tags = Column(JsonVariant)
    language = Column(String)              # language of title/description/content (en|he)
    source_snapshot = Column(JsonVariant)  # exact scraped context used for generation
    source_published_at = Column(DateTime)

    content_items = relationship("ContentItem", back_populates="property")
    property_images = relationship("PropertyImage", back_populates="property")
    generated_media = relationship("GeneratedMedia",
                                   foreign_keys="GeneratedMedia.property_id",
                                   back_populates="property")


class GeneratedMedia(Base):
    __tablename__ = "generated_media"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), index=True, nullable=True)
    content_id = Column(
        Integer,
        ForeignKey(
            "content_items.id",
            use_alter=True,
            name="fk_generated_media_content_id_content_items",
        ),
        index=True,
        nullable=True,
    )
    media_type = Column(String, nullable=False)          # IMAGE | VIDEO
    provider = Column(String)                            # SCRAPED | OPENAI | FFMPEG | PILLOW
    file_name = Column(String)
    prompt = Column(Text)
    storage_url = Column(Text)
    storage_key = Column(String)
    file_token = Column(String, unique=True, index=True)
    size_bytes = Column(Integer)
    sha256 = Column(String)
    thumbnail_url = Column(Text)
    mime_type = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    duration_seconds = Column(Integer)
    generation_status = Column(String, default='PENDING', nullable=False)  # PENDING|GENERATING|COMPLETED|FAILED
    error = Column(Text)
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    property = relationship("Property",
                            foreign_keys=[property_id],
                            back_populates="generated_media")
    content_items = relationship("ContentItem",
                                 foreign_keys="ContentItem.media_id",
                                 back_populates="media")
    content = relationship(
        "ContentItem", foreign_keys=[content_id], post_update=True, overlaps="content_items,media"
    )


class PropertyImage(Base):
    __tablename__ = "property_images"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    source_url = Column(Text)
    status = Column(String, default='PENDING', nullable=False)   # PENDING|VALID|BROKEN
    failure_reason = Column(Text)
    media_id = Column(Integer, ForeignKey("generated_media.id"), nullable=True)
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    checked_at = Column(DateTime)

    property = relationship("Property", back_populates="property_images")
    media = relationship("GeneratedMedia", foreign_keys=[media_id])


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint(
            'property_id', 'generation_date', 'kind', 'variant_number', 'language',
            name='uq_content_items_v3'
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"))
    kind = Column(String)   # post|story
    platform = Column(String, index=True)
    language = Column(String, index=True)
    caption = Column(Text)
    hashtags = Column(JsonVariant)
    cta = Column(String)
    link = Column(String)
    image_path = Column(String)            # legacy – kept for compat; superseded by media_id
    theme = Column(String)
    scheduled_at = Column(DateTime, index=True)
    status = Column(String, default="draft", index=True)  # kept as derived / legacy compat
    review_notes = Column(Text)
    review_score = Column(Float)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    published_at = Column(DateTime)

    # New columns
    variant_number = Column(Integer)
    angle = Column(String)           # PROPERTY_HIGHLIGHT|DESTINATION|EMOTIONAL | HOOK|MESSAGE|CTA
    title = Column(String)
    generation_date = Column(String, index=True)
    media_id = Column(Integer, ForeignKey("generated_media.id"), nullable=True)
    approval_status = Column(String, default='PENDING')     # PENDING|APPROVED|REJECTED
    publish_status = Column(String, default='DRAFT')        # DRAFT|SCHEDULED|PUBLISHED|FAILED
    rejection_reason = Column(Text)
    story_hook = Column(Text)
    story_message = Column(Text)
    visual_concept = Column(Text)
    generation_status = Column(String, default='PENDING')   # PENDING|PROCESSING|SUCCESS|FAILED
    error = Column(Text)

    # Spec additions
    platform_targets = Column(JsonVariant)                  # ["instagram","facebook",...]
    contact_email = Column(String)
    source_snapshot = Column(JsonVariant)
    generation_mode = Column(String)                        # HUMAN | AUTOMATION
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    property = relationship("Property", back_populates="content_items")
    publish_logs = relationship(
        "PublishLog",
        foreign_keys="PublishLog.content_item_id",
        back_populates="content_item",
    )
    media = relationship("GeneratedMedia",
                         foreign_keys=[media_id],
                         back_populates="content_items")


class PublishLog(Base):
    """One row per (content, platform): the same content can go to many platforms."""
    __tablename__ = "publish_logs"
    __table_args__ = (UniqueConstraint("content_id", "platform", name="uq_publish_logs_content_platform"),)

    id = Column(Integer, primary_key=True, index=True)
    content_item_id = Column(Integer, ForeignKey("content_items.id"), index=True)
    platform = Column(String)
    status = Column(String)
    response = Column(JsonVariant)
    error = Column(Text)
    attempt = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    # New columns
    content_id = Column(Integer, ForeignKey("content_items.id"), index=True)
    published_at = Column(DateTime)
    external_post_id = Column(String)
    scheduled_at = Column(DateTime)
    is_demo = Column(Boolean, default=True, nullable=False)   # True = DEMO PUBLISHED (no real API call)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    content_item = relationship(
        "ContentItem", foreign_keys=[content_item_id], back_populates="publish_logs"
    )
    content = relationship("ContentItem", foreign_keys=[content_id])


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)
    agent = Column(String)
    status = Column(String)
    provider = Column(String)
    duration_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True)   # PROPERTY_AUTO_APPROVED, CONTENT_AUTO_APPROVED, etc.
    entity_type = Column(String)
    entity_id = Column(Integer)
    mode = Column(String)
    status = Column(String)
    error = Column(Text)
    language = Column(String)
    platform = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, unique=True, index=True)
    plan = Column(JsonVariant)
    created_at = Column(DateTime, server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(JsonVariant)
