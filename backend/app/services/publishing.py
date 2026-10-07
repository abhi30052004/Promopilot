"""PublishingService: publish / schedule one content item to many platforms.

Every (content, platform) pair owns exactly one PublishLog row, so the same content can be
PUBLISHED on Instagram, SCHEDULED on LinkedIn and FAILED on Facebook at the same time.

Providers live in ``app.adapters``. Without real credentials a platform is served by the
DemoPublishingProvider (``MockPublisher``): the log is flagged ``is_demo=True`` and shown as
"DEMO PUBLISHED". Nothing here ever claims a real Instagram/Facebook/LinkedIn call was made.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.config import get_settings
from app.models import ContentItem, GeneratedMedia, Property, PublishLog
from concurrent.futures import ThreadPoolExecutor

from app.services.events import SUPPORTED_PLATFORMS, get_mode, get_setting, log_event

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


class PublishError(ValueError):
    """Validation failure (maps to HTTP 409/422 in the API layer)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_platforms(platforms: Optional[Iterable[str]]) -> list[str]:
    cleaned = list(dict.fromkeys(str(p).strip().lower() for p in (platforms or []) if str(p).strip()))
    unknown = [p for p in cleaned if p not in SUPPORTED_PLATFORMS]
    if unknown:
        raise PublishError(f"Unsupported platform(s): {', '.join(unknown)}")
    if not cleaned:
        raise PublishError("Select at least one platform")
    return cleaned


def validate_content(item: ContentItem, db: Session, require_media_ready: bool = True) -> None:
    if item.approval_status == "REJECTED":
        raise PublishError("Rejected content can never be published or scheduled")
    prop = db.query(Property).filter(Property.id == item.property_id).first()
    if not prop or prop.approval_status != "APPROVED":
        raise PublishError("The linked property must be approved before content can be published")
    if not (item.caption or item.story_hook):
        raise PublishError("Content has no text")
    if not item.media_id:
        raise PublishError("Content has no media")
    media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first()
    if not media:
        raise PublishError("Content media record is missing")
    if require_media_ready and (media.generation_status != "COMPLETED" or not media.storage_url):
        raise PublishError(f"Media is not ready yet (status: {media.generation_status})")


def _get_log(db: Session, item: ContentItem, platform: str) -> PublishLog:
    log = (
        db.query(PublishLog)
        .filter(PublishLog.content_id == item.id, PublishLog.platform == platform)
        .first()
    )
    if not log:
        log = PublishLog(content_item_id=item.id, content_id=item.id, platform=platform,
                         status="SCHEDULED", attempt=0, is_demo=True)
        db.add(log)
        db.flush()
    return log


def refresh_item_status(item: ContentItem, db: Session) -> None:
    """Derive the content-level publish_status from its per-platform logs."""
    logs = db.query(PublishLog).filter(PublishLog.content_id == item.id).all()
    statuses = {(log.status or "").upper() for log in logs}
    if "SCHEDULED" in statuses:
        item.publish_status = "SCHEDULED"
        item.status = "scheduled"
        times = [log.scheduled_at for log in logs if (log.status or "").upper() == "SCHEDULED" and log.scheduled_at]
        if times:
            item.scheduled_at = min(times)
    elif "PUBLISHED" in statuses:
        item.publish_status = "PUBLISHED"
        item.status = "published"
        item.published_at = max((log.published_at for log in logs if log.published_at), default=_utcnow())
    elif "FAILED" in statuses:
        item.publish_status = "FAILED"
        item.status = "failed"
    else:
        item.publish_status = "DRAFT"
        item.status = "approved" if item.approval_status == "APPROVED" else "pending_approval"
    item.platform_targets = list(dict.fromkeys(
        list(item.platform_targets or []) + [log.platform for log in logs]
    ))
    db.commit()


def _call_provider(platform: str, item: ContentItem) -> dict:
    """Run the provider (network/simulated latency) with retries. No database access."""
    adapter = get_adapter(platform)
    result: dict = {}
    for _attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = adapter.publish(item)
        except Exception as exc:  # provider crashed -> record, retry
            result = {"status": "failed", "error": str(exc), "demo": True}
        if result.get("status") == "success":
            break
    result["_attempts"] = _attempt
    return result


def publish_many(item: ContentItem, platforms: list[str], db: Session) -> list[PublishLog]:
    """Publish to several platforms at once: providers run in parallel, DB writes are batched."""
    logs = {p: _get_log(db, item, p) for p in platforms}
    todo = [p for p in platforms if (logs[p].status or "").upper() != "PUBLISHED"]
    if todo:
        # make sure relationships a provider may read are loaded before leaving this thread
        _ = item.media
        with ThreadPoolExecutor(max_workers=len(todo)) as pool:
            results = dict(zip(todo, pool.map(lambda p: _call_provider(p, item), todo)))
        mode = get_mode(db)
        now = _utcnow()
        for platform in todo:
            result = results[platform]
            ok = result.get("status") == "success"
            log = logs[platform]
            log.attempt = result.pop("_attempts", 1)
            log.status = "PUBLISHED" if ok else "FAILED"
            log.response = result
            log.is_demo = bool(result.get("demo", True))
            log.error = None if ok else (result.get("error") or "Publishing failed")
            log.published_at = now if ok else None
            log.external_post_id = (
                result.get("external_id") or result.get("post_id") or result.get("message_id")
            ) if ok else None
            log_event(
                db, "POST_PUBLISHED" if ok else "POST_FAILED", "content_item", item.id,
                "SUCCESS" if ok else "FAILED", error=log.error, language=item.language,
                platform=platform, mode=mode, commit=False,
            )
        db.commit()
    return [logs[p] for p in platforms]


class PublishingService:
    """publish(content, platform) / schedule(content, platform, datetime)."""

    @staticmethod
    def publish(item: ContentItem, platform: str, db: Session) -> PublishLog:
        """Publish now to one platform (idempotent: an already PUBLISHED log is returned as-is)."""
        log = _get_log(db, item, platform)
        if (log.status or "").upper() == "PUBLISHED":
            return log
        adapter = get_adapter(platform)
        result: dict = {}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            log.attempt = attempt
            try:
                result = adapter.publish(item)
            except Exception as exc:  # provider crashed -> record, retry
                result = {"status": "failed", "error": str(exc), "demo": True}
            if result.get("status") == "success":
                break
        ok = result.get("status") == "success"
        now = _utcnow()
        log.status = "PUBLISHED" if ok else "FAILED"
        log.response = result
        log.is_demo = bool(result.get("demo", True))
        log.error = None if ok else (result.get("error") or "Publishing failed")
        log.published_at = now if ok else None
        log.external_post_id = (
            result.get("external_id") or result.get("post_id") or result.get("message_id")
        ) if ok else None
        db.commit()
        log_event(
            db, "POST_PUBLISHED" if ok else "POST_FAILED", "content_item", item.id,
            "SUCCESS" if ok else "FAILED", error=log.error, language=item.language, platform=platform,
        )
        return log

    @staticmethod
    def schedule(item: ContentItem, platform: str, when: datetime, db: Session) -> PublishLog:
        """Create/refresh the SCHEDULED log of one platform (``when`` is naive UTC)."""
        log = _get_log(db, item, platform)
        if (log.status or "").upper() == "PUBLISHED":
            return log
        log.status = "SCHEDULED"
        log.scheduled_at = when
        log.error = None
        log.attempt = 0
        db.commit()
        log_event(db, "POST_SCHEDULED", "content_item", item.id, "SUCCESS", language=item.language,
                  platform=platform)
        return log


def _mark_approved(item: ContentItem, platforms: list[str]) -> None:
    item.approval_status = "APPROVED"
    item.rejection_reason = None
    item.platform_targets = platforms
    item.platform = platforms[0]


def _drop_unselected_scheduled(item: ContentItem, platforms: list[str], db: Session) -> None:
    for log in db.query(PublishLog).filter(PublishLog.content_id == item.id).all():
        if log.platform not in platforms and (log.status or "").upper() == "SCHEDULED":
            db.delete(log)
    db.flush()


def approve_and_publish(item: ContentItem, platforms: Iterable[str], db: Session) -> list[PublishLog]:
    platforms = normalize_platforms(platforms)
    validate_content(item, db)
    was_approved = item.approval_status == "APPROVED"
    _mark_approved(item, platforms)
    _drop_unselected_scheduled(item, platforms, db)
    db.commit()
    if not was_approved:
        log_event(db, "CONTENT_APPROVED", "content_item", item.id, language=item.language)
    logs = publish_many(item, platforms, db)
    refresh_item_status(item, db)
    return logs


def approve_and_schedule(
    item: ContentItem, platforms: Iterable[str], when: datetime, db: Session
) -> list[PublishLog]:
    platforms = normalize_platforms(platforms)
    validate_content(item, db, require_media_ready=False)
    if when <= _utcnow():
        raise PublishError("The scheduled time must be in the future")
    was_approved = item.approval_status == "APPROVED"
    _mark_approved(item, platforms)
    _drop_unselected_scheduled(item, platforms, db)
    db.commit()
    if not was_approved:
        log_event(db, "CONTENT_APPROVED", "content_item", item.id, language=item.language)
    logs = [PublishingService.schedule(item, platform, when, db) for platform in platforms]
    refresh_item_status(item, db)
    return logs


def retry_failed(item: ContentItem, db: Session, platform: Optional[str] = None) -> list[PublishLog]:
    validate_content(item, db)
    failed = [
        log for log in db.query(PublishLog).filter(PublishLog.content_id == item.id).all()
        if (log.status or "").upper() == "FAILED" and (platform is None or log.platform == platform)
    ]
    if not failed:
        raise PublishError("There is no failed publish to retry")
    out = []
    for log in failed:
        log.status = "SCHEDULED"
        db.commit()
        out.append(PublishingService.publish(item, log.platform, db))
    refresh_item_status(item, db)
    return out


def _slot_time(db: Session, item: ContentItem) -> Optional[datetime]:
    key = "post_slots" if item.kind == "post" else "story_slots"
    default = ["09:00", "15:00", "19:00"] if item.kind == "post" else ["11:00", "17:00", "20:00"]
    slots = get_setting(db, key, default)
    slot = slots[((item.variant_number or 1) - 1) % len(slots)]
    try:
        tz = ZoneInfo(get_settings().TIMEZONE)
        local = datetime.fromisoformat(f"{item.generation_date}T{slot}:00").replace(tzinfo=tz)
        return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def auto_approve_and_schedule(item: ContentItem, db: Session, platforms: list[str]) -> None:
    """AUTOMATION mode: AI approves the content and schedules it on the configured platforms.

    A slot that is already in the past is moved to "now + a minute" (staggered by variant) so the
    scheduler publishes it right away. Story videos may still be rendering; the scheduler waits
    for the media to be COMPLETED before publishing.
    """
    platforms = normalize_platforms(platforms)
    now = _utcnow()
    when = _slot_time(db, item)
    stagger = timedelta(minutes=1 + (item.variant_number or 1) - 1)
    if not when or when <= now + timedelta(seconds=30):
        when = now + stagger
    _mark_approved(item, platforms)
    db.commit()
    log_event(db, "AUTO_APPROVED", "content_item", item.id, language=item.language, mode="AUTOMATION")
    for platform in platforms:
        PublishingService.schedule(item, platform, when, db)
    refresh_item_status(item, db)


def reject_item(item: ContentItem, reason: Optional[str], db: Session) -> None:
    if item.publish_status == "PUBLISHED":
        raise PublishError("Cannot reject an already published item")
    for log in db.query(PublishLog).filter(PublishLog.content_id == item.id).all():
        if (log.status or "").upper() in ("SCHEDULED", "FAILED"):
            db.delete(log)  # rejected content must never be published
    item.approval_status = "REJECTED"
    item.publish_status = "DRAFT"
    item.status = "rejected"
    item.scheduled_at = None
    if reason:
        item.rejection_reason = reason
    db.commit()
    log_event(db, "CONTENT_REJECTED", "content_item", item.id, language=item.language)


def publish_due(db: Session) -> int:
    """Scheduler job: publish every SCHEDULED log whose time has come. Returns #processed."""
    now = _utcnow()
    due = (
        db.query(PublishLog)
        .filter(PublishLog.status == "SCHEDULED", PublishLog.scheduled_at.is_not(None),
                PublishLog.scheduled_at <= now)
        .order_by(PublishLog.scheduled_at.asc())
        .all()
    )
    processed = 0
    touched: dict[int, ContentItem] = {}
    for log in due:
        item = db.query(ContentItem).filter(ContentItem.id == log.content_id).first()
        if not item:
            continue
        touched[item.id] = item
        if item.approval_status != "APPROVED":
            db.delete(log)  # rejected/unapproved content is never published
            db.commit()
            continue
        media = db.query(GeneratedMedia).filter(GeneratedMedia.id == item.media_id).first() if item.media_id else None
        if media and media.generation_status in ("PENDING", "GENERATING"):
            continue  # video still rendering; try again on the next tick
        try:
            validate_content(item, db)
        except PublishError as exc:
            log.status = "FAILED"
            log.error = str(exc)
            db.commit()
            log_event(db, "POST_FAILED", "content_item", item.id, "FAILED", error=str(exc),
                      language=item.language, platform=log.platform)
            processed += 1
            continue
        PublishingService.publish(item, log.platform, db)
        processed += 1
    for item in touched.values():
        refresh_item_status(item, db)
    return processed
