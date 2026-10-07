"""
Content generation service (Milestone 4).

POST /api/properties/{id}/generate-content
Generates exactly:
  - 3 POSTS with angles: PROPERTY_HIGHLIGHT, DESTINATION, EMOTIONAL
  - 3 STORIES with angles: HOOK, MESSAGE, CTA

Rules:
- Property must be APPROVED
- Idempotent by (property_id, generation_date) unless force=True
- Platform rules, language settings
- Links images and triggers story video generation
"""
import logging
import time
import uuid
from datetime import datetime, date
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    AgentLog, AutomationLog, ContentItem, GeneratedMedia,
    Property, PropertyImage, PublishLog, Setting
)
from app.services.llm import generate_openai_json, LLMError
from app.services.media_storage import save_generated_media
from app.services.image_validator import ensure_at_least_one_image, validate_property_images
from app.services.vectorstore import index_content

logger = logging.getLogger(__name__)
settings = get_settings()


class PostContent(BaseModel):
    title: str = Field(..., description="Short post title")
    caption: str = Field(..., description="Post caption text")
    hashtags: str = Field(..., description="Space-separated hashtags")
    cta: str = Field(..., description="Call-to-action text")
    link: str = Field(..., description="Property URL")
    visual_concept: str = Field("", description="Brief visual description for image selection")


class StoryContent(BaseModel):
    title: str = Field(..., description="Short internal story title")
    story_hook: str = Field(..., description="Hook line (0-3s), 1-2 sentences")
    story_message: str = Field(..., description="Main message (3-7s), 1-2 sentences")
    cta: str = Field(..., description="CTA for the 7-10s section")
    visual_concept: str = Field("", description="Brief visual concept")
    caption: str = Field("", description="Full caption if needed")
    hashtags: str = Field("", description="1-2 hashtags")
    link: str = Field("", description="Property URL")


POST_ANGLES = ["PROPERTY_HIGHLIGHT", "DESTINATION", "EMOTIONAL"]
STORY_ANGLES = ["HOOK", "MESSAGE", "CTA"]


def _get_settings_dict(db: Session) -> dict:
    rows = db.query(Setting).all()
    return {s.key: s.value for s in rows}


def _scheduled_slot(generation_date: str, slot: str) -> Optional[datetime]:
    try:
        local = datetime.fromisoformat(f"{generation_date}T{slot}:00").replace(
            tzinfo=ZoneInfo(settings.TIMEZONE)
        )
        return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _pick_best_image(prop: Property, db: Session) -> Optional[GeneratedMedia]:
    """Return the best available image for this property."""
    # Prefer a valid scraped image
    valid_pi = (
        db.query(PropertyImage)
        .filter(
            PropertyImage.property_id == prop.id,
            PropertyImage.status == "VALID",
            PropertyImage.media_id != None,
        )
        .first()
    )
    if valid_pi and valid_pi.media_id:
        m = db.query(GeneratedMedia).filter(GeneratedMedia.id == valid_pi.media_id).first()
        if m and m.storage_url:
            return m

    # Fall back to any completed AI image
    return (
        db.query(GeneratedMedia)
        .filter(
            GeneratedMedia.property_id == prop.id,
            GeneratedMedia.media_type == "IMAGE",
            GeneratedMedia.generation_status == "COMPLETED",
        )
        .first()
    )


def _generate_post(
    prop: Property,
    angle: str,
    variant_number: int,
    platform: str,
    language: str,
    generation_date: str,
    brand_tone: str,
    platforms_enabled: list,
    db: Session,
    run_id: str,
) -> Optional[ContentItem]:
    angle_desc = {
        "PROPERTY_HIGHLIGHT": "Focus on the property itself: features, amenities, unique selling points, the experience of staying there.",
        "DESTINATION": "Focus on the location, nearby attractions (only if present in the data), the travel experience and Northern Israel scenery.",
        "EMOTIONAL": "Focus on emotions: relaxation, vacation mood, inspiration, escape from daily life.",
    }

    platform_rules = {
        "instagram": "Emotional and visual. Include 8-12 hashtags.",
        "facebook": "Informative, medium length.",
        "tiktok": "Short hook followed by concise caption.",
        "x": "CRITICAL: entire text (caption + cta + link) MUST be under 280 characters.",
        "telegram": "Longer and informative, provide all useful details.",
    }

    lang_rule = "Write in natural Israeli Hebrew." if language == "he" else "Write in natural English."
    amenities_str = ""
    if prop.amenities:
        if isinstance(prop.amenities, list):
            amenities_str = ", ".join(str(a) for a in prop.amenities[:15])
        else:
            amenities_str = str(prop.amenities)

    sys_prompt = f"""You are a top-tier Social Media Copywriter for vacation rentals in Northern Israel.
Brand Tone: {brand_tone}
Target Language: {lang_rule}
Content Angle: {angle} – {angle_desc.get(angle, '')}
Platform: {platform}
Platform Rules: {platform_rules.get(platform, '')}

CRITICAL RULES:
- Use ONLY the verified facts provided. NEVER invent prices, amenities, availability, discounts, addresses, or any claim not in the data.
- If a fact is missing, leave it out. Do not guess.
- Each post must have a DIFFERENT angle/theme from the other 2 posts – do NOT reword the same caption.
- ALWAYS include the property URL in the 'link' field.
- Return valid JSON matching the schema exactly.
"""

    prompt = f"""Verified Property Facts:
Name: {prop.name}
Type: {prop.type or 'vacation property'}
Location: {prop.location or 'Northern Israel'}
Description: {(prop.description or '')[:500]}
Amenities: {amenities_str}
URL: {prop.url or ''}
Generation Date: {generation_date}
Variant: {variant_number} of 3 (ensure this is distinct from the others)

Write post variant {variant_number} for {platform} in {language}, angle {angle}.
Return fields: title, caption, hashtags, cta, link, visual_concept.
"""

    start = time.time()
    try:
        result = generate_openai_json(prompt, sys_prompt, PostContent)
        duration_ms = int((time.time() - start) * 1000)
        db.add(AgentLog(
            run_id=run_id,
            agent="content_writer_post",
            status="success",
            provider="openai",
            duration_ms=duration_ms,
            message=f"Post {angle} variant {variant_number} generated",
        ))
        db.commit()
    except LLMError as exc:
        logger.error(f"Post generation failed for {prop.id} angle={angle}: {exc}")
        return None

    # Pick scheduled_at from settings slots
    settings_dict = _get_settings_dict(db)
    post_slots = settings_dict.get("post_slots", ["09:00", "15:00", "19:00"])
    slot = post_slots[(variant_number - 1) % len(post_slots)]
    sch_at = _scheduled_slot(generation_date, slot)

    item = ContentItem(
        property_id=prop.id,
        kind="post",
        platform=platform,
        language=language,
        angle=angle,
        variant_number=variant_number,
        generation_date=generation_date,
        caption=result.caption,
        hashtags=result.hashtags,
        cta=result.cta,
        link=prop.url or result.link,
        visual_concept=result.visual_concept,
        scheduled_at=sch_at,
        title=result.title,
        status="pending_approval",
        approval_status="PENDING",
        publish_status="DRAFT",
        generation_status="SUCCESS",
        retry_count=0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Attach image
    best_image = _pick_best_image(prop, db)
    if not best_image:
        db.delete(item)
        db.commit()
        logger.error("Discarded post %s because no persistent image was available", item.id)
        return None
    item.media_id = best_image.id
    item.image_path = best_image.storage_url  # keep legacy field in sync
    db.commit()

    try:
        index_content(item)
    except Exception:
        pass

    return item


def _generate_story(
    prop: Property,
    angle: str,
    variant_number: int,
    platform: str,
    language: str,
    generation_date: str,
    brand_tone: str,
    db: Session,
    run_id: str,
) -> Optional[ContentItem]:
    angle_desc = {
        "HOOK": "Start with 'Looking for your next escape?' style hook. Create intrigue and desire.",
        "MESSAGE": "Nature and atmosphere. Describe the peaceful experience, the surroundings, the feeling.",
        "CTA": "Booking CTA style. 'Ready for your next stay?' – drive action.",
    }

    lang_rule = "Write in natural Israeli Hebrew." if language == "he" else "Write in natural English."
    amenities_str = ""
    if prop.amenities:
        if isinstance(prop.amenities, list):
            amenities_str = ", ".join(str(a) for a in prop.amenities[:10])
        else:
            amenities_str = str(prop.amenities)

    sys_prompt = f"""You are a Social Media Story Copywriter for vacation rentals in Northern Israel.
Brand Tone: {brand_tone}
Target Language: {lang_rule}
Story Angle: {angle} – {angle_desc.get(angle, '')}
Platform: {platform}

CRITICAL RULES:
- Stories are SHORT: 1-2 lines per section.
- story_hook: the opening 3 seconds – must grab attention immediately.
- story_message: the middle 4 seconds – atmosphere, feeling, key fact.
- cta: the final 3 seconds – action text only (e.g., "הזמינו עכשיו" / "Book now").
- Use ONLY verified property facts. Never invent.
- Return valid JSON matching the schema exactly.
"""

    prompt = f"""Verified Property Facts:
Name: {prop.name}
Location: {prop.location or 'Northern Israel'}
Description: {(prop.description or '')[:300]}
Amenities: {amenities_str}
URL: {prop.url or ''}

Write story variant {variant_number} angle {angle} for {platform} in {language}.
Return fields: title, story_hook, story_message, cta, visual_concept, caption,
hashtags, and link.
"""

    start = time.time()
    try:
        result = generate_openai_json(prompt, sys_prompt, StoryContent)
        duration_ms = int((time.time() - start) * 1000)
        db.add(AgentLog(
            run_id=run_id,
            agent="content_writer_story",
            status="success",
            provider="openai",
            duration_ms=duration_ms,
            message=f"Story {angle} variant {variant_number} generated",
        ))
        db.commit()
    except LLMError as exc:
        logger.error(f"Story generation failed for {prop.id} angle={angle}: {exc}")
        return None

    settings_dict = _get_settings_dict(db)
    story_slots = settings_dict.get("story_slots", ["11:00", "17:00", "20:00"])
    slot = story_slots[(variant_number - 1) % len(story_slots)]
    sch_at = _scheduled_slot(generation_date, slot)

    item = ContentItem(
        property_id=prop.id,
        kind="story",
        platform=platform,
        language=language,
        angle=angle,
        variant_number=variant_number,
        generation_date=generation_date,
        caption=result.caption or result.story_hook,
        hashtags=result.hashtags or "",
        cta=result.cta,
        link=prop.url or result.link,
        story_hook=result.story_hook,
        story_message=result.story_message,
        title=result.title,
        visual_concept=result.visual_concept,
        scheduled_at=sch_at,
        status="pending_approval",
        approval_status="PENDING",
        publish_status="DRAFT",
        generation_status="SUCCESS",
        retry_count=0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # A story receives a VIDEO GeneratedMedia row immediately, before FFmpeg starts.
    try:
        best_image = _pick_best_image(prop, db)
        from app.services.video_generator import queue_story_video
        queue_story_video(item, best_image.id if best_image else None, db)
    except Exception as exc:
        logger.warning(f"Video trigger failed for story {item.id}: {exc}")
        db.delete(item)
        db.commit()
        return None

    if not item.media_id:
        db.delete(item)
        db.commit()
        logger.error("Discarded story %s because no persistent video record was created", item.id)
        return None

    try:
        index_content(item)
    except Exception:
        pass

    return item


def generate_content_for_property(
    prop: Property,
    db: Session,
    generation_date: Optional[str] = None,
    force: bool = False,
) -> dict:
    """
    Main entry point.  Returns {"posts": [...], "stories": [...], "skipped": bool}.
    """
    if prop.approval_status != "APPROVED":
        raise ValueError("Property must be APPROVED before content generation")

    gen_date = generation_date or datetime.now(ZoneInfo(settings.TIMEZONE)).date().isoformat()

    existing_items = db.query(ContentItem).filter(
        ContentItem.property_id == prop.id,
        ContentItem.generation_date == gen_date,
    ).all()
    existing_keys = {(item.kind, item.variant_number) for item in existing_items}
    if len(existing_keys) >= 6 and not force:
        return {"posts": [], "stories": [], "skipped": True, "reason": "already_generated"}

    run_id = str(uuid.uuid4())
    settings_dict = _get_settings_dict(db)
    brand_tone = settings_dict.get("brand_tone", "relaxing")
    languages = settings_dict.get("languages", ["he", "en"])
    platforms_enabled = settings_dict.get("platforms_enabled", ["instagram", "facebook", "tiktok", "x", "telegram"])

    # Choose language: first in the list
    lang = languages[0] if languages else "he"
    # Choose platform cycling through the list
    def _platform(idx):
        return platforms_enabled[idx % len(platforms_enabled)] if platforms_enabled else "instagram"

    # Ensure every generated item can reference persistent media before drafting it.
    prop.content_generation_status = "PROCESSING"
    db.commit()
    try:
        base_media = ensure_at_least_one_image(prop, db) or _pick_best_image(prop, db)
    except Exception as exc:
        prop.content_generation_status = "FAILED"
        db.add(AutomationLog(
            action="CONTENT_GENERATION_FAILED",
            entity_type="property",
            entity_id=prop.id,
            mode=str(settings_dict.get("approval_mode", "HUMAN")),
            status="FAILED",
            error=str(exc),
        ))
        db.commit()
        raise RuntimeError(str(exc)) from exc
    if not base_media:
        error = "No usable persistent image is available for content generation"
        prop.content_generation_status = "FAILED"
        db.add(AutomationLog(
            action="CONTENT_GENERATION_FAILED",
            entity_type="property",
            entity_id=prop.id,
            mode=str(settings_dict.get("approval_mode", "HUMAN")),
            status="FAILED",
            error=error,
        ))
        db.commit()
        raise RuntimeError(error)

    posts = []
    stories = []
    errors = []

    for i, angle in enumerate(POST_ANGLES):
        if ("post", i + 1) in existing_keys:
            continue
        item = _generate_post(
            prop, angle, i + 1, _platform(i), lang, gen_date,
            brand_tone, platforms_enabled, db, run_id
        )
        if item:
            posts.append(item.id)
        else:
            errors.append(f"post_{angle}_failed")

    for i, angle in enumerate(STORY_ANGLES):
        if ("story", i + 1) in existing_keys:
            continue
        item = _generate_story(
            prop, angle, i + 1, _platform(i), lang, gen_date,
            brand_tone, db, run_id
        )
        if item:
            stories.append(item.id)
        else:
            errors.append(f"story_{angle}_failed")

    prop.content_generation_status = "SUCCESS" if not errors else "FAILED"
    db.commit()

    # Automation approves and schedules; the scheduler performs the actual publish.
    mode = settings_dict.get("approval_mode", "HUMAN")
    generated_ids = posts + stories
    if str(mode).upper() == "AUTOMATION":
        generated_items = db.query(ContentItem).filter(ContentItem.id.in_(generated_ids)).all()
        for item in generated_items:
            item.approval_status = "APPROVED"
            item.publish_status = "SCHEDULED"
            item.status = "scheduled"
            db.add(AutomationLog(
                action="CONTENT_AUTO_APPROVED",
                entity_type="content_item",
                entity_id=item.id,
                mode="AUTOMATION",
                status="SUCCESS",
            ))
            db.add(AutomationLog(
                action="POST_SCHEDULED",
                entity_type="content_item",
                entity_id=item.id,
                mode="AUTOMATION",
                status="SUCCESS",
            ))
            db.add(PublishLog(
                content_item_id=item.id,
                content_id=item.id,
                platform=item.platform,
                status="scheduled",
                attempt=0,
            ))
        db.commit()

    db.add(AutomationLog(
        action="CONTENT_GENERATED",
        entity_type="property",
        entity_id=prop.id,
        mode=mode,
        status="SUCCESS" if not errors else ("PARTIAL" if generated_ids else "FAILED"),
        error="; ".join(errors) if errors else None,
    ))
    db.commit()

    return {
        "posts": posts,
        "stories": stories,
        "errors": errors,
        "skipped": False,
        "generation_date": gen_date,
    }
