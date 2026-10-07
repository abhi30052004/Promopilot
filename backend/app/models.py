from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, UniqueConstraint
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
    images = Column(JsonVariant)
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    content_items = relationship("ContentItem", back_populates="property")

class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint('property_id', 'kind', 'platform', 'scheduled_at', 'language', name='uq_content_items'),
    )

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"))
    kind = Column(String) # post/story
    platform = Column(String, index=True)
    language = Column(String, index=True)
    caption = Column(Text)
    hashtags = Column(JsonVariant)
    cta = Column(String)
    link = Column(String)
    image_path = Column(String)
    theme = Column(String)
    scheduled_at = Column(DateTime, index=True)
    status = Column(String, default="draft", index=True)
    review_notes = Column(Text)
    review_score = Column(Float)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    published_at = Column(DateTime)

    property = relationship("Property", back_populates="content_items")
    publish_logs = relationship("PublishLog", back_populates="content_item")

class PublishLog(Base):
    __tablename__ = "publish_logs"

    id = Column(Integer, primary_key=True, index=True)
    content_item_id = Column(Integer, ForeignKey("content_items.id"), index=True)
    platform = Column(String)
    status = Column(String)
    response = Column(JsonVariant)
    error = Column(Text)
    attempt = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    content_item = relationship("ContentItem", back_populates="publish_logs")

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
