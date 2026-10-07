from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime

class PropertyBase(BaseModel):
    name: str
    slug: str
    type: Optional[str] = None
    description: Optional[str] = None
    amenities: Optional[Any] = None
    location: Optional[str] = None
    url: Optional[str] = None
    images: Optional[Any] = None
    last_synced_at: Optional[datetime] = None

class PropertyCreate(PropertyBase):
    pass

class PropertyRead(PropertyBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ContentItemBase(BaseModel):
    property_id: Optional[int] = None
    kind: Optional[str] = None
    platform: Optional[str] = None
    language: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[Any] = None
    cta: Optional[str] = None
    link: Optional[str] = None
    image_path: Optional[str] = None
    theme: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: str = "draft"
    review_notes: Optional[str] = None
    review_score: Optional[float] = None
    retry_count: int = 0
    published_at: Optional[datetime] = None

class ContentItemCreate(ContentItemBase):
    pass

class ContentItemRead(ContentItemBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PublishLogBase(BaseModel):
    content_item_id: Optional[int] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    response: Optional[Any] = None
    error: Optional[str] = None
    attempt: Optional[int] = None

class PublishLogCreate(PublishLogBase):
    pass

class PublishLogRead(PublishLogBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AgentLogBase(BaseModel):
    run_id: Optional[str] = None
    agent: Optional[str] = None
    status: Optional[str] = None
    provider: Optional[str] = None
    duration_ms: Optional[int] = None
    retry_count: int = 0
    message: Optional[str] = None

class AgentLogCreate(AgentLogBase):
    pass

class AgentLogRead(AgentLogBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DailyPlanBase(BaseModel):
    date: Optional[str] = None
    plan: Optional[Any] = None

class DailyPlanCreate(DailyPlanBase):
    pass

class DailyPlanRead(DailyPlanBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SettingBase(BaseModel):
    key: str
    value: Optional[Any] = None

class SettingCreate(SettingBase):
    pass

class SettingRead(SettingBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
