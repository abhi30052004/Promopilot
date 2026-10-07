"""Create persistent ten-second vertical story videos with FFmpeg."""
from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AutomationLog, ContentItem, GeneratedMedia, Setting
from app.services.media_storage import (
    complete_media,
    create_pending_media,
    read_media_bytes,
)

logger = logging.getLogger(__name__)

VIDEO_W, VIDEO_H = 1080, 1920
FPS = 30
DURATION = 10


def _ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _font(size: int) -> ImageFont.FreeTypeFont:
    font_path = Path(__file__).resolve().parents[2] / "fonts" / "Heebo-Bold.ttf"
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def _wrap(text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    for word in (text or "").split():
        candidate = " ".join(current + [word])
        width = font.getlength(candidate) if hasattr(font, "getlength") else font.getsize(candidate)[0]
        if current and width > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines[:5]


def _text_overlay(text: str, size: int = 80) -> Image.Image:
    canvas = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(size)
    lines = _wrap(text, font, VIDEO_W - 140)
    line_height = size + 20
    y = (VIDEO_H - len(lines) * line_height) // 2
    for line in lines:
        display = get_display(line)
        width = font.getlength(display) if hasattr(font, "getlength") else font.getsize(display)[0]
        x = (VIDEO_W - width) // 2
        draw.text((x + 4, y + 4), display, font=font, fill=(0, 0, 0, 210))
        draw.text((x, y), display, font=font, fill=(255, 255, 255, 245))
        y += line_height
    return canvas


def _cta_overlay(text: str) -> Image.Image:
    canvas = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(70)
    display = get_display(text)
    width = font.getlength(display) if hasattr(font, "getlength") else font.getsize(display)[0]
    bar_y = VIDEO_H - 260
    draw.rounded_rectangle((60, bar_y, VIDEO_W - 60, bar_y + 150), 32, fill=(220, 50, 50, 235))
    draw.text(
        ((VIDEO_W - width) // 2, bar_y + 35),
        display,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return canvas


def _vertical_background(source_bytes: Optional[bytes]) -> Image.Image:
    if source_bytes:
        image = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    else:
        image = Image.new("RGB", (VIDEO_W, VIDEO_H), (24, 31, 60))
    width, height = image.size
    target_ratio = VIDEO_W / VIDEO_H
    if width / height > target_ratio:
        crop_width = int(height * target_ratio)
        left = (width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, height))
    else:
        crop_height = int(width / target_ratio)
        top = (height - crop_height) // 2
        image = image.crop((0, top, width, top + crop_height))
    return image.resize((VIDEO_W, VIDEO_H), Image.Resampling.LANCZOS)


def _build_video(item: ContentItem, source_bytes: Optional[bytes]) -> bytes:
    hook = item.story_hook or item.caption or "Discover your next escape"
    message = item.story_message or item.caption or ""
    cta = item.cta or ("Book now" if item.language != "he" else "הזמינו עכשיו")

    with tempfile.TemporaryDirectory() as tmpdir:
        background_path = os.path.join(tmpdir, "background.jpg")
        hook_path = os.path.join(tmpdir, "hook.png")
        message_path = os.path.join(tmpdir, "message.png")
        cta_path = os.path.join(tmpdir, "cta.png")
        output_path = os.path.join(tmpdir, "story.mp4")

        _vertical_background(source_bytes).save(background_path, "JPEG", quality=92)
        _text_overlay(hook, 90).save(hook_path, "PNG")
        _text_overlay(message, 72).save(message_path, "PNG")
        _cta_overlay(cta).save(cta_path, "PNG")

        command = [
            _ffmpeg_path(),
            "-y",
            "-loop",
            "1",
            "-t",
            str(DURATION),
            "-i",
            background_path,
            "-i",
            hook_path,
            "-i",
            message_path,
            "-i",
            cta_path,
            "-filter_complex",
            (
                f"[0:v]scale={VIDEO_W}:{VIDEO_H},"
                f"zoompan=z='min(zoom+0.0005,1.05)':x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':d={DURATION * FPS}:s={VIDEO_W}x{VIDEO_H}:fps={FPS}[z];"
                "[z][1:v]overlay=0:0:enable='between(t,0,3)'[v1];"
                "[v1][2:v]overlay=0:0:enable='between(t,3,7)'[v2];"
                "[v2][3:v]overlay=0:0:enable='between(t,7,10)'[out]"
            ),
            "-map",
            "[out]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-movflags",
            "+faststart",
            "-t",
            str(DURATION),
            output_path,
        ]
        result = subprocess.run(command, capture_output=True, timeout=180)
        if result.returncode != 0:
            error = result.stderr.decode(errors="replace")[-2000:]
            raise RuntimeError(f"FFmpeg failed: {error}")
        data = Path(output_path).read_bytes()
        if not data:
            raise RuntimeError("FFmpeg created an empty video")
        return data


def _mode(db: Session) -> str:
    row = db.query(Setting).filter(Setting.key == "approval_mode").first()
    return str(row.value if row else "HUMAN")


def _log(db: Session, action: str, entity_id: int, status: str, error: str | None = None) -> None:
    db.add(
        AutomationLog(
            action=action,
            entity_type="generated_media",
            entity_id=entity_id,
            mode=_mode(db),
            status=status,
            error=error,
        )
    )
    db.commit()


def generate_story_video(
    item: ContentItem,
    source_media: Optional[GeneratedMedia],
    media: GeneratedMedia,
    db: Session,
) -> Optional[GeneratedMedia]:
    """Complete a pre-created VIDEO record and link it to the story."""
    _log(db, "VIDEO_GENERATION_STARTED", media.id, "STARTED")
    try:
        source_bytes = read_media_bytes(source_media) if source_media else None
        video_bytes = _build_video(item, source_bytes)
        complete_media(
            db,
            media,
            video_bytes,
            mime_type="video/mp4",
            ext="mp4",
            width=VIDEO_W,
            height=VIDEO_H,
            duration=DURATION,
        )
        item.media_id = media.id
        item.error = None
        db.commit()
        _log(db, "VIDEO_GENERATED", media.id, "SUCCESS")
        return media
    except Exception as exc:
        logger.exception("Story video generation failed for content %s", item.id)
        media.generation_status = "FAILED"
        media.error = str(exc)
        item.error = str(exc)
        db.commit()
        _log(db, "VIDEO_GENERATION_FAILED", media.id, "FAILED", str(exc))
        return None


def _run_video_job(content_id: int, media_id: int, source_media_id: Optional[int]) -> None:
    db = SessionLocal()
    try:
        item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
        media = db.query(GeneratedMedia).filter(GeneratedMedia.id == media_id).first()
        source = (
            db.query(GeneratedMedia).filter(GeneratedMedia.id == source_media_id).first()
            if source_media_id
            else None
        )
        if item and media:
            generate_story_video(item, source, media, db)
    finally:
        db.close()


def queue_story_video(
    item: ContentItem, source_media_id: Optional[int], db: Session, force: bool = False
) -> GeneratedMedia:
    """Create the required database record first, then start FFmpeg in the background."""
    existing = (
        db.query(GeneratedMedia)
        .filter(
            GeneratedMedia.content_id == item.id,
            GeneratedMedia.media_type == "VIDEO",
            GeneratedMedia.generation_status.in_(["PENDING", "GENERATING", "COMPLETED"]),
        )
        .order_by(GeneratedMedia.created_at.desc())
        .first()
    )
    if existing and not force:
        item.media_id = existing.id
        db.commit()
        return existing

    media = create_pending_media(
        db,
        property_id=item.property_id,
        content_id=item.id,
        media_type="VIDEO",
        provider="FFMPEG",
        mime_type="video/mp4",
        is_ai=False,
    )
    item.media_id = media.id
    db.commit()
    thread = threading.Thread(
        target=_run_video_job,
        args=(item.id, media.id, source_media_id),
        daemon=True,
    )
    thread.start()
    return media
