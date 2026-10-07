"""Scraper for tzelahahar.co.il/en/articles.

Article pages are server-rendered by TanStack Start. The article record is embedded in the
streamed ``$R`` hydration payload as a JavaScript object literal (``article:$R[14]={...}``),
which carries the full text in English/Hebrew/Spanish. We parse that literal directly instead
of guessing at DOM selectors: it is the exact data the site renders.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models import Property
from app.services.events import log_event

logger = logging.getLogger(__name__)

SITE = "https://tzelahahar.co.il"
_HEBREW = re.compile(r"[֐-׿]")
_REF = re.compile(r"\$R\[\d+\]=")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")


def detect_language(text: Optional[str]) -> str:
    """Cheap, deterministic language guess: Hebrew letters dominate => 'he', else 'en'."""
    if not text:
        return "en"
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    hebrew = sum(1 for c in letters if _HEBREW.match(c))
    return "he" if hebrew / len(letters) > 0.3 else "en"


class _JsLiteral:
    """Tiny recursive-descent parser for the JS literal subset emitted by seroval ($R payload)."""

    def __init__(self, text: str, pos: int):
        self.s = text
        self.i = pos

    def _ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t\r\n":
            self.i += 1

    def value(self) -> Any:
        self._ws()
        m = _REF.match(self.s, self.i)  # "$R[14]=" reference-assignment prefix
        if m:
            self.i = m.end()
            return self.value()
        c = self.s[self.i]
        if c == "{":
            return self._object()
        if c == "[":
            return self._array()
        if c == '"':
            return self._string()
        for literal, val in (("null", None), ("!0", True), ("!1", False), ("void 0", None), ("undefined", None)):
            if self.s.startswith(literal, self.i):
                self.i += len(literal)
                return val
        m = _NUMBER.match(self.s, self.i)
        if m:
            self.i = m.end()
            text = m.group(0)
            return float(text) if any(ch in text for ch in ".eE") else int(text)
        raise ValueError(f"Unsupported literal at {self.i}: {self.s[self.i:self.i + 30]!r}")

    def _string(self) -> str:
        start = self.i
        self.i += 1
        while self.s[self.i] != '"':
            self.i += 2 if self.s[self.i] == "\\" else 1
        self.i += 1
        raw = self.s[start:self.i]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw[1:-1].replace('\\"', '"').replace("\\n", "\n")

    def _object(self) -> dict:
        self.i += 1
        out: dict = {}
        while True:
            self._ws()
            if self.s[self.i] == "}":
                self.i += 1
                return out
            if self.s[self.i] == ",":
                self.i += 1
                continue
            if self.s[self.i] == '"':
                key = self._string()
            else:
                m = _IDENT.match(self.s, self.i)
                if not m:
                    raise ValueError(f"Bad object key at {self.i}")
                key = m.group(0)
                self.i = m.end()
            self._ws()
            if self.s[self.i] != ":":
                raise ValueError(f"Expected ':' at {self.i}")
            self.i += 1
            out[key] = self.value()

    def _array(self) -> list:
        self.i += 1
        out = []
        while True:
            self._ws()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            if self.s[self.i] == ",":
                self.i += 1
                continue
            out.append(self.value())


def extract_article_record(html: str) -> Optional[dict]:
    m = re.search(r"article:(?:\$R\[\d+\]=)?\{", html)
    if not m:
        return None
    try:
        return _JsLiteral(html, m.end() - 1).value()
    except Exception as exc:
        logger.warning("Could not parse article payload: %s", exc)
        return None


def _prettify_region(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    return str(region).replace("_", " ").replace("-", " ").title()


def parse_article_page(html: str, url: str) -> Optional[dict]:
    """Return normalized article data from a rendered article page, or None if not an article."""
    record = extract_article_record(html)
    soup = BeautifulSoup(html, "html.parser")

    json_ld: dict = {}
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, json.JSONDecodeError):
            continue
        for item in payload if isinstance(payload, list) else [payload]:
            if isinstance(item, dict) and item.get("@type") == "Article":
                json_ld = item

    if not record and not json_ld:
        return None
    record = record or {}

    title = record.get("title_en") or json_ld.get("headline")
    if not title:
        return None
    content = record.get("content_en") or None
    excerpt = record.get("excerpt_en") or json_ld.get("description") or None

    keywords_meta = soup.find("meta", attrs={"name": "keywords"})
    keywords = [k.strip() for k in (keywords_meta.get("content", "") if keywords_meta else "").split(",") if k.strip()]

    cover = record.get("cover_image")
    image_urls: list[str] = []
    if isinstance(cover, str) and cover and not cover.startswith("editorial:"):
        image_urls.append(urljoin(SITE, cover))

    published = record.get("created_at") or json_ld.get("datePublished")
    try:
        published_dt = (
            datetime.fromisoformat(str(published).replace("Z", "+00:00")).replace(tzinfo=None) if published else None
        )
    except ValueError:
        published_dt = None

    slug = record.get("slug") or urlparse(url).path.rstrip("/").split("/")[-1]
    article_type = record.get("type")
    title_lower = str(title).lower()
    keywords = [k for k in keywords if k.lower() not in title_lower]  # the meta tag repeats title fragments
    tags = list(dict.fromkeys([t for t in [article_type, record.get("region")] if t] + keywords))

    return {
        "slug": slug,
        "name": title,
        "url": f"{SITE}/en/articles/{slug}",
        "description": excerpt,
        "content": content,
        "summary": excerpt,
        "location": _prettify_region(record.get("region")),
        "category": article_type,
        "tags": tags,
        "image_urls": image_urls,
        "published_at": published_dt,
        "language": "en",
        "extra": {
            "title_he": record.get("title_he"),
            "excerpt_he": record.get("excerpt_he"),
            "content_he": record.get("content_he"),
            "event_schedule": record.get("event_schedule"),
            "region": record.get("region"),
            "article_id": record.get("id"),
            "cover_image": cover,
        },
    }


def build_snapshot(prop: Property, scraped_at: datetime, extra: Optional[dict] = None) -> dict:
    """Exact scraped context used for AI generation (reproducibility + prompt-safety audit)."""
    snapshot = {
        "title": prop.title or prop.name,
        "description": prop.description,
        "content": prop.content,
        "summary": prop.summary,
        "location": prop.location,
        "category": prop.category,
        "amenities": prop.amenities or [],
        "images": prop.images or [],
        "url": prop.source_url or prop.url,
        "language": prop.language,
        "scraped_at": scraped_at.isoformat(),
    }
    if extra:
        snapshot["extra"] = extra
    return snapshot


def sync_articles(db: Session, fetch_html, extract_sitemap_urls, base_url: str = SITE) -> dict:
    """Scrape every English article in the sitemap into ``properties`` (type='article')."""
    results = {"created": 0, "updated": 0, "failed": 0, "errors": [], "property_ids": []}

    urls = [u for u in extract_sitemap_urls(base_url) if re.search(r"/en/articles/[^/]+/?$", u)]
    urls = list(dict.fromkeys(urls))
    logger.info("Found %s English article URLs", len(urls))

    for url in urls:
        try:
            html, _ = fetch_html(url)
            if not html:
                results["failed"] += 1
                results["errors"].append({"url": url, "error": "No HTML returned"})
                continue
            data = parse_article_page(html, url)
            if not data:
                results["failed"] += 1
                results["errors"].append({"url": url, "error": "Not a parseable article"})
                continue

            now = datetime.utcnow()
            prop = db.query(Property).filter(Property.source_url == data["url"]).first()
            slug = f"article-{data['slug']}"
            if not prop:
                prop = db.query(Property).filter(Property.slug == slug).first()
            is_new = prop is None
            if is_new:
                prop = Property(
                    slug=slug,
                    approval_status="PENDING",
                    media_status="PENDING",
                    content_generation_status="NONE",
                )
                db.add(prop)

            prop.name = data["name"]
            prop.title = data["name"]
            prop.type = "article"
            prop.category = data["category"] or "article"
            prop.description = data["description"]
            prop.content = data["content"]
            prop.summary = data["summary"]
            prop.location = data["location"]
            prop.tags = data["tags"]
            prop.amenities = []
            prop.url = data["url"]
            prop.source_url = data["url"]
            prop.language = data["language"]
            prop.source_published_at = data["published_at"]
            if data["image_urls"]:
                prop.images = data["image_urls"]
            elif is_new:
                prop.images = []
            prop.scraped_at = now
            prop.last_synced_at = now
            prop.source_snapshot = build_snapshot(prop, now, data["extra"])
            db.commit()
            db.refresh(prop)

            results["created" if is_new else "updated"] += 1
            results["property_ids"].append(prop.id)
            log_event(db, "SCRAPED", "property", prop.id, "SUCCESS", language=prop.language)
        except Exception as exc:
            logger.error("Error scraping article %s: %s", url, exc)
            db.rollback()
            results["failed"] += 1
            results["errors"].append({"url": url, "error": str(exc)})
    return results
