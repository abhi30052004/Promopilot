import io
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    ContentItem,
    GeneratedMedia,
    Property,
    PropertyImage,
    PublishLog,
    Setting,
)
from app.routers.auth import get_current_user


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = lambda: "admin"
client = TestClient(app)


@pytest.fixture(autouse=True)
def database(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    defaults = {
        "approval_mode": "HUMAN",
        "story_duration_seconds": 10,
        "max_ai_images_per_property": 3,
        "brand_tone": "relaxing",
        "languages": ["en"],
        "platforms_enabled": ["instagram", "facebook", "x"],
        "post_slots": ["09:00", "15:00", "19:00"],
        "story_slots": ["11:00", "17:00", "20:00"],
    }
    db.add_all([Setting(key=key, value=value) for key, value in defaults.items()])
    db.commit()
    db.close()

    # Endpoint background work uses the production session factory; isolate it here.
    monkeypatch.setattr("app.routers.properties._process_property_bg", lambda *args: None)
    yield
    Base.metadata.drop_all(bind=engine)


def image_bytes(color=(40, 100, 160)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(output, "JPEG")
    return output.getvalue()


def test_live_site_json_ld_property_parser():
    from app.services.ingestion import parse_property_page

    html = """
    <html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"LodgingBusiness","name":"Test Stay",
     "description":"Verified description","url":"https://example.com/properties/test-stay-123",
     "address":{"addressLocality":"Safed","addressRegion":"Galilee"},
     "image":[{"contentUrl":"https://images.example/stay.jpg"}]}
    </script></head><body>
    <script>amenities:$R[15]=["WiFi","Pool"],price_per_night:750</script>
    </body></html>
    """
    parsed = parse_property_page(html, "https://example.com/properties/test-stay-123")
    assert parsed["name"] == "Test Stay"
    assert parsed["location"] == "Safed, Galilee"
    assert parsed["amenities"] == ["WiFi", "Pool"]
    assert parsed["price"] == "750"
    assert parsed["image_urls"] == ["https://images.example/stay.jpg"]


def add_property(db, *, status="PENDING", slug="test-villa") -> Property:
    prop = Property(
        name="Test Villa",
        slug=slug,
        source_url="https://example.com/test-villa",
        url="https://example.com/test-villa",
        description="A quiet villa surrounded by trees.",
        location="Northern Israel",
        amenities=["pool", "garden"],
        images=["https://example.com/broken.jpg"],
        approval_status=status,
        media_status="PENDING",
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


def add_completed_media(db, prop, *, content=None, media_type="IMAGE") -> GeneratedMedia:
    media = GeneratedMedia(
        property_id=prop.id,
        content_id=content.id if content else None,
        media_type=media_type,
        provider="TEST",
        storage_url=f"https://media.example/{prop.id}/{media_type.lower()}",
        storage_key=f"key-{prop.id}-{media_type}",
        file_token=f"token-{prop.id}-{media_type}-{content.id if content else 0}",
        mime_type="video/mp4" if media_type == "VIDEO" else "image/jpeg",
        generation_status="COMPLETED",
        duration_seconds=10 if media_type == "VIDEO" else None,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    if content:
        content.media_id = media.id
        db.commit()
    return media


def test_property_approval_and_rejection_guards():
    db = TestingSessionLocal()
    prop = add_property(db)

    listing = client.get("/api/properties")
    assert listing.status_code == 200
    assert listing.json()[0]["approval_status"] == "PENDING"

    rejected = client.post(f"/api/properties/{prop.id}/reject", json={"reason": "Incomplete"})
    assert rejected.status_code == 200
    blocked = client.post(f"/api/properties/{prop.id}/generate-content", json={})
    assert blocked.status_code == 400

    db.refresh(prop)
    prop.approval_status = "PENDING"
    db.commit()
    approved = client.post(f"/api/properties/{prop.id}/approve")
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "APPROVED"
    assert approved.json()["id"] == prop.id
    assert approved.json()["name"] == prop.name
    db.close()


def test_broken_image_creates_persistent_ai_replacement(monkeypatch, tmp_path):
    from app.services import image_validator, media_storage

    storage = media_storage.LocalStorage(str(tmp_path))
    monkeypatch.setattr(media_storage, "get_storage", lambda: storage)
    monkeypatch.setattr(
        image_validator,
        "_validate_and_download",
        lambda *args: (None, None, "HTTP 403"),
    )
    monkeypatch.setattr(image_validator, "_generate_ai_image", lambda prop: image_bytes())

    db = TestingSessionLocal()
    prop = add_property(db, status="APPROVED")
    image_validator.validate_property_images(prop, db)

    row = db.query(PropertyImage).filter(PropertyImage.property_id == prop.id).one()
    media = db.query(GeneratedMedia).filter(GeneratedMedia.id == row.media_id).one()
    assert row.status == "BROKEN"
    assert row.is_ai_generated is True
    assert media.provider == "OPENAI"
    assert media.generation_status == "COMPLETED"
    assert media.storage_url and media.mime_type == "image/jpeg"
    assert (tmp_path / media.storage_key).exists()

    # A new SQLAlchemy session simulates a backend restart: metadata and bytes survive.
    media_id = media.id
    db.close()
    restarted = TestingSessionLocal()
    persisted = restarted.query(GeneratedMedia).filter(GeneratedMedia.id == media_id).one()
    assert (tmp_path / persisted.storage_key).read_bytes()
    restarted.close()


def test_exact_three_posts_three_stories_and_idempotency(monkeypatch):
    from app.services import content_generator, video_generator

    def fake_llm(_prompt, _system, schema):
        if schema is content_generator.PostContent:
            marker = _prompt.split("Variant: ", 1)[1].split(" ", 1)[0]
            return schema(
                title=f"Post {marker}",
                caption=f"Distinct post caption {marker}",
                hashtags=f"#post{marker}",
                cta="Book now",
                link="https://example.com/test-villa",
                visual_concept=f"Concept {marker}",
            )
        marker = _prompt.split("variant ", 1)[1].split(" ", 1)[0]
        return schema(
            title=f"Story {marker}",
            story_hook=f"Story hook {marker}",
            story_message=f"Story message {marker}",
            cta="Book now",
            visual_concept=f"Story concept {marker}",
            caption=f"Story caption {marker}",
            hashtags=f"#story{marker}",
            link="https://example.com/test-villa",
        )

    def fake_queue(item, _source_media_id, db, force=False):
        return add_completed_media(db, item.property, content=item, media_type="VIDEO")

    monkeypatch.setattr(content_generator, "generate_openai_json", fake_llm)
    monkeypatch.setattr(content_generator, "ensure_at_least_one_image", lambda prop, db: None)
    monkeypatch.setattr(video_generator, "queue_story_video", fake_queue)
    monkeypatch.setattr(content_generator, "index_content", lambda item: None)

    db = TestingSessionLocal()
    prop = add_property(db, status="APPROVED")
    image = add_completed_media(db, prop)
    db.add(PropertyImage(property_id=prop.id, source_url=prop.images[0], status="VALID", media_id=image.id))
    db.commit()

    result = content_generator.generate_content_for_property(prop, db, "2026-10-08")
    assert len(result["posts"]) == 3
    assert len(result["stories"]) == 3
    items = db.query(ContentItem).filter(ContentItem.property_id == prop.id).all()
    assert len(items) == 6
    assert len({item.caption for item in items if item.kind == "post"}) == 3
    assert {item.variant_number for item in items if item.kind == "story"} == {1, 2, 3}
    assert all(item.media_id for item in items)
    assert all(item.approval_status == "PENDING" for item in items)

    repeated = content_generator.generate_content_for_property(prop, db, "2026-10-08")
    assert repeated["skipped"] is True
    assert db.query(ContentItem).filter(ContentItem.property_id == prop.id).count() == 6

    mode = db.query(Setting).filter(Setting.key == "approval_mode").one()
    mode.value = "AUTOMATION"
    db.commit()
    automated = content_generator.generate_content_for_property(prop, db, "2026-10-09")
    auto_items = db.query(ContentItem).filter(
        ContentItem.id.in_(automated["posts"] + automated["stories"])
    ).all()
    assert len(auto_items) == 6
    assert all(item.approval_status == "APPROVED" for item in auto_items)
    assert all(item.publish_status == "SCHEDULED" for item in auto_items)
    assert db.query(PublishLog).filter(PublishLog.status == "scheduled").count() == 6
    db.close()


def test_publish_schedule_reject_and_feeds():
    db = TestingSessionLocal()
    prop = add_property(db, status="APPROVED")

    publish_item = ContentItem(
        property_id=prop.id,
        kind="post",
        platform="instagram",
        language="en",
        caption="Publish me",
        approval_status="PENDING",
        publish_status="DRAFT",
        status="pending_approval",
    )
    schedule_item = ContentItem(
        property_id=prop.id,
        kind="story",
        platform="instagram",
        language="en",
        caption="Schedule me",
        approval_status="PENDING",
        publish_status="DRAFT",
        status="pending_approval",
    )
    reject_item = ContentItem(
        property_id=prop.id,
        kind="post",
        platform="facebook",
        language="en",
        caption="Reject me",
        approval_status="PENDING",
        publish_status="DRAFT",
        status="pending_approval",
    )
    db.add_all([publish_item, schedule_item, reject_item])
    db.commit()
    for item, media_type in ((publish_item, "IMAGE"), (schedule_item, "VIDEO"), (reject_item, "IMAGE")):
        add_completed_media(db, prop, content=item, media_type=media_type)

    published = client.post(f"/api/content/{publish_item.id}/publish")
    assert published.status_code == 200 and published.json()["publish_status"] == "PUBLISHED"

    future = (
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)
    ).isoformat(timespec="minutes")
    scheduled = client.post(
        f"/api/content/{schedule_item.id}/schedule",
        json={"scheduled_at": future, "platform": "facebook"},
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["publish_status"] == "SCHEDULED"

    calendar = client.get(
        "/api/calendar",
        params={"start": future[:10], "end": future[:10]},
    )
    assert calendar.status_code == 200
    assert [row["id"] for row in calendar.json()] == [schedule_item.id]
    assert calendar.json()[0]["property_name"] == prop.name

    rejected = client.post(f"/api/content/{reject_item.id}/reject", json={"reason": "No"})
    assert rejected.status_code == 200
    assert client.post(f"/api/content/{reject_item.id}/publish").status_code == 409

    db.expire_all()
    assert db.query(PublishLog).filter(PublishLog.content_item_id == publish_item.id).count() == 1
    assert db.query(PublishLog).filter(PublishLog.content_item_id == schedule_item.id, PublishLog.status == "scheduled").count() == 1
    feed = client.get("/api/feeds").json()
    assert {item["publish_status"] for item in feed} == {"PUBLISHED", "SCHEDULED"}
    assert all(item["media_url"] for item in feed)

    unapproved_prop = add_property(db, slug="pending-villa")
    blocked_item = ContentItem(
        property_id=unapproved_prop.id,
        kind="post",
        platform="instagram",
        language="en",
        caption="Must stay blocked",
        approval_status="APPROVED",
        publish_status="DRAFT",
        status="approved",
    )
    db.add(blocked_item)
    db.commit()
    add_completed_media(db, unapproved_prop, content=blocked_item)
    assert client.post(f"/api/content/{blocked_item.id}/publish").status_code == 409
    db.close()


def test_tokenized_media_file_is_public_and_range_capable(monkeypatch, tmp_path):
    from app.routers import media as media_router
    from app.services import media_storage

    storage = media_storage.LocalStorage(str(tmp_path))
    monkeypatch.setattr(media_storage, "get_storage", lambda: storage)
    monkeypatch.setattr(media_router, "get_storage", lambda: storage)

    db = TestingSessionLocal()
    prop = add_property(db, status="APPROVED")
    media = media_storage.save_generated_media(
        db,
        image_bytes(),
        prop.id,
        None,
        "IMAGE",
        "SCRAPED",
        "image/jpeg",
        "jpg",
    )
    path = urlsplit(media.storage_url).path + "?" + urlsplit(media.storage_url).query
    db.close()

    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    ranged = client.get(path, headers={"Range": "bytes=0-9"})
    assert ranged.status_code == 206
    assert len(ranged.content) == 10
