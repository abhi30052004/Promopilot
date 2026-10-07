import logging
import os
import time
import uuid
import io
import json
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from PIL import Image
from slugify import slugify
from sqlalchemy.orm import Session

from app.models import Property
from app.services.events import log_event
from app.services.articles import build_snapshot, detect_language
from app.config import get_settings
from app.services.parser_config import ParserConfig
from app.services.vectorstore import index_property

logger = logging.getLogger(__name__)
settings = get_settings()

def get_browser_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

def fetch_html(url: str, retries: int = 3) -> Tuple[Optional[str], bool]:
    """Fetch HTML using httpx only (no headless browser). Returns (html, False)."""
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=15.0, headers=get_browser_headers(), follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text, False
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2)

    logger.error(f"All retries failed for {url}")
    return None, False

def extract_sitemap_urls(url: str) -> List[str]:
    """Try to find URLs from sitemaps."""
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    sitemap_urls = [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml")
    ]
    
    urls = set()
    for s_url in sitemap_urls:
        try:
            with httpx.Client(timeout=10.0, headers=get_browser_headers(), follow_redirects=True) as client:
                response = client.get(s_url)
                if response.status_code == 200:
                    logger.info(f"Found sitemap at {s_url}")
                    soup = BeautifulSoup(response.content, "xml")
                    for loc in soup.find_all("loc"):
                        urls.add(loc.text)
        except Exception as e:
            logger.warning(f"Failed to fetch sitemap {s_url}: {e}")
            
    return list(urls)

def discover_urls_from_page(url: str, html: str) -> List[str]:
    """Find property links from homepage/menu."""
    soup = BeautifulSoup(html, "html.parser")
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    
    discovered = set()
    for a in soup.select(ParserConfig.NAV_LINKS_SELECTOR):
        href = a.get("href")
        if not href:
            continue
        
        full_url = urljoin(base_url, href)
        parsed_url = urlparse(full_url)
        
        # Only keep links to same domain
        if parsed_url.netloc != urlparse(base_url).netloc:
            continue
            
        discovered.add(full_url)
            
    return list(discovered)

def download_image(img_url: str, slug: str) -> Optional[str]:
    """Download image, check size, save to MEDIA_DIR, return relative path."""
    try:
        with httpx.Client(timeout=10.0, headers=get_browser_headers(), follow_redirects=True) as client:
            response = client.get(img_url)
            if response.status_code != 200:
                return None
            
            img_data = response.content
            # Check size with PIL
            img = Image.open(io.BytesIO(img_data))
            width, height = img.size
            if width < 400:
                logger.info(f"Skipping small image {img_url} ({width}x{height})")
                return None
                
            # Convert format if needed
            ext = img.format.lower() if img.format else "jpg"
            if ext == "jpeg": ext = "jpg"
            if ext == "svg" or ext == "webp": # Handle webp/svg
                pass
            
            filename = f"{uuid.uuid4().hex[:8]}.{ext}"
            save_dir = os.path.join(settings.MEDIA_DIR, "original", slug)
            os.makedirs(save_dir, exist_ok=True)
            
            save_path = os.path.join(save_dir, filename)
            # Save original bytes to preserve quality
            with open(save_path, "wb") as f:
                f.write(img_data)
                
            rel_path = f"original/{slug}/{filename}"
            return rel_path
    except Exception as e:
        logger.warning(f"Failed to download image {img_url}: {e}")
        return None

def parse_property_page(html: str, url: str) -> Optional[Dict]:
    """Parse HTML to extract property info."""
    soup = BeautifulSoup(html, "html.parser")

    # The current source renders property details through React server payloads,
    # but also exposes stable schema.org LodgingBusiness JSON-LD. Prefer that
    # machine-readable source and retain the selector parser as a legacy fallback.
    lodging = None
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        lodging = next(
            (
                item for item in candidates
                if isinstance(item, dict) and item.get("@type") in {"LodgingBusiness", "Hotel", "VacationRental"}
            ),
            lodging,
        )

    if lodging:
        name = str(lodging.get("name") or "").strip()
        if not name:
            return None
        address = lodging.get("address") if isinstance(lodging.get("address"), dict) else {}
        location = ", ".join(
            value for value in (address.get("addressLocality"), address.get("addressRegion")) if value
        ) or None
        images = lodging.get("image") or []
        if not isinstance(images, list):
            images = [images]
        image_urls = []
        for image in images:
            if isinstance(image, str):
                image_urls.append(image)
            elif isinstance(image, dict):
                image_url = image.get("contentUrl") or image.get("url")
                if image_url:
                    image_urls.append(image_url)

        amenities = []
        amenities_match = re.search(r"amenities:\$R\[\d+\]=(\[[^\]]*\])", html)
        if amenities_match:
            try:
                parsed_amenities = json.loads(amenities_match.group(1))
                if isinstance(parsed_amenities, list):
                    amenities = parsed_amenities
            except json.JSONDecodeError:
                pass

        price = None
        price_match = re.search(r"price_per_night:(null|\d+(?:\.\d+)?)", html)
        if price_match and price_match.group(1) != "null":
            price = price_match.group(1)

        canonical_url = lodging.get("url") or url
        canonical_path_slug = urlparse(canonical_url).path.rstrip("/").split("/")[-1]
        slug = slugify(canonical_path_slug or name, max_length=100, word_boundary=True, allow_unicode=True)
        return {
            "name": name,
            "slug": slug or uuid.uuid4().hex[:8],
            "url": canonical_url,
            "description": lodging.get("description") or None,
            "location": location,
            "type": lodging.get("@type"),
            "price": price,
            "amenities": amenities,
            "image_urls": list(dict.fromkeys(image_urls)),
        }

    name_el = soup.select_one(ParserConfig.NAME_SELECTOR)
    if not name_el:
        return None # Name is critical, probably not a property page
    
    name = name_el.get_text(strip=True)
    slug = slugify(name, max_length=100, word_boundary=True, allow_unicode=True)
    if not slug:
        slug = slugify(urlparse(url).path.strip("/"), allow_unicode=True)
        if not slug:
            slug = uuid.uuid4().hex[:8]

    desc_parts = [el.get_text(separator=' ', strip=True) for el in soup.select(ParserConfig.DESCRIPTION_SELECTOR)]
    description = "\n\n".join(part for part in desc_parts if part)
    
    location_el = soup.select_one(ParserConfig.LOCATION_SELECTOR)
    location = location_el.get_text(strip=True) if location_el else None
    
    type_el = soup.select_one(ParserConfig.TYPE_SELECTOR)
    type_str = type_el.get_text(strip=True) if type_el else None

    price_el = soup.select_one(ParserConfig.PRICE_SELECTOR)
    price = price_el.get_text(" ", strip=True) if price_el else None
    
    amenities = [el.get_text(strip=True) for el in soup.select(ParserConfig.AMENITIES_SELECTOR)]
    
    # Extract image URLs
    image_urls = []
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    for img in soup.select(ParserConfig.IMAGES_SELECTOR):
        src = img.get("src") or img.get("data-src")
        if src:
            image_urls.append(urljoin(base_url, src))
            
    # Remove duplicates
    image_urls = list(dict.fromkeys(image_urls))
    
    return {
        "name": name,
        "slug": slug,
        "url": url,
        "description": description or None,
        "location": location,
        "type": type_str,
        "price": price,
        "amenities": amenities if amenities else [],
        "image_urls": image_urls
    }

def sync_site(url: str, db: Session) -> Dict:
    results = {"created": 0, "updated": 0, "failed": 0, "errors": [], "property_ids": []}
    logger.info(f"Starting sync for {url}")

    # The English articles section is scraped by the dedicated article parser.
    if "/articles" in urlparse(url).path:
        from app.services.articles import sync_articles

        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        return sync_articles(db, fetch_html, extract_sitemap_urls, base)
    
    urls_to_process = extract_sitemap_urls(url)
    
    if not urls_to_process:
        logger.info(f"No sitemap URLs found, parsing homepage {url}")
        html, _ = fetch_html(url)
        if html:
            urls_to_process = discover_urls_from_page(url, html)
            
    logger.info(f"Discovered {len(urls_to_process)} URLs. Filtering for properties...")
    
    # Prefer one canonical URL per property slug. The source sitemap contains
    # translated duplicates (/en/properties/... and /es/properties/...), while
    # the root /properties/... URL is the canonical record used by the demo.
    property_candidates = {}
    for u in urls_to_process:
        path = urlparse(u).path.lower()
        if any(p in path for p in ParserConfig.PROPERTY_URL_PATTERNS) or not ParserConfig.PROPERTY_URL_PATTERNS:
            key = path.rstrip("/").split("/")[-1]
            rank = 0 if path.startswith("/properties/") else (1 if path.startswith("/en/") else 2)
            current = property_candidates.get(key)
            if not current or rank < current[0]:
                property_candidates[key] = (rank, u)

    property_urls = [candidate[1] for candidate in property_candidates.values()]
            
    if not property_urls and urls_to_process and not ParserConfig.PROPERTY_URL_PATTERNS:
        property_urls = urls_to_process

    logger.info(f"Processing {len(property_urls)} potential property pages...")
    
    for p_url in property_urls:
        try:
            logger.info(f"Processing page: {p_url}")
            html, _ = fetch_html(p_url)
            if not html:
                results["failed"] += 1
                results["errors"].append({"url": p_url, "error": "No HTML returned"})
                continue
                
            prop_data = parse_property_page(html, p_url)
            if not prop_data:
                logger.info(f"Could not extract property data from {p_url} (no name found).")
                continue
                
            slug = prop_data["slug"]
            
            # Upsert DB Check
            db_prop = db.query(Property).filter(Property.slug == slug).first()
            if not db_prop:
                db_prop = db.query(Property).filter(Property.url == p_url).first()
                
            is_new = db_prop is None
            
            if is_new:
                db_prop = Property(
                    name=prop_data["name"],
                    slug=slug,
                    url=p_url,
                    source_url=p_url,
                    title=prop_data["name"],
                    type=prop_data["type"],
                    category=prop_data["type"],
                    price=prop_data["price"],
                    description=prop_data["description"],
                    location=prop_data["location"],
                    amenities=prop_data["amenities"],
                    # Keep source URLs so validation can verify and persist them.
                    images=prop_data["image_urls"][:15],
                    approval_status="PENDING",
                    media_status="PENDING",
                    content_generation_status="NONE",
                    scraped_at=datetime.utcnow(),
                    last_synced_at=datetime.utcnow(),
                )
                db.add(db_prop)
                results["created"] += 1
            else:
                db_prop.name = prop_data["name"]
                db_prop.type = prop_data["type"]
                db_prop.description = prop_data["description"]
                db_prop.location = prop_data["location"]
                db_prop.amenities = prop_data["amenities"]
                db_prop.url = p_url
                db_prop.source_url = p_url
                db_prop.title = prop_data["name"]
                db_prop.category = prop_data["type"]
                db_prop.price = prop_data["price"]
                if prop_data["image_urls"]:
                    db_prop.images = prop_data["image_urls"][:15]
                db_prop.last_synced_at = datetime.utcnow()
                db_prop.scraped_at = datetime.utcnow()
                results["updated"] += 1

            # Full scraped context + reproducible snapshot (spec sections 3 and 49).
            db_prop.content = prop_data["description"]
            db_prop.summary = (prop_data["description"] or "")[:300] or None
            db_prop.language = detect_language(prop_data["description"] or prop_data["name"])
            db_prop.source_snapshot = build_snapshot(db_prop, datetime.utcnow())
            db.commit()
            db.refresh(db_prop)
            results["property_ids"].append(db_prop.id)

            log_event(db, "SCRAPED", "property", db_prop.id, "SUCCESS", language=db_prop.language)
            
            # Index property in vector store
            index_property(db_prop)
            
        except Exception as e:
            logger.error(f"Error syncing {p_url}: {e}")
            results["failed"] += 1
            results["errors"].append({"url": p_url, "error": str(e)})
            db.rollback()
            
    return results
