import logging
from pydantic import BaseModel

from app.services.llm import generate_openai_json
from app.models import ContentItem

logger = logging.getLogger(__name__)

from typing import Optional

class TranslationResult(BaseModel):
    caption: str
    hashtags: Optional[str] = ""
    cta: Optional[str] = ""
    link: Optional[str] = ""

def translate_item(item: ContentItem, target_lang: str) -> ContentItem:
    """Translates a content item to the target language via OpenAI."""
    sys_prompt = f"""You are an expert content translator for social media. Translate the given content into '{target_lang}'.
Rules:
- Preserve property names as accurately as possible (transliterate or keep in original if it makes sense).
- Preserve all URLs exactly.
- Keep the platform's specific limits (e.g., X limit is 280 characters, stories are 1-2 lines).
- DO NOT add any new facts, claims, prices, or amenities.
- Return ONLY valid JSON matching the schema.
"""
    
    prompt = f"""Content to translate:
Platform: {item.platform}
Kind: {item.kind}
Caption: {item.caption}
Hashtags: {item.hashtags}
CTA: {item.cta}
Link: {item.link}
"""

    res = generate_openai_json(prompt, sys_prompt, TranslationResult)
    
    new_item = ContentItem(
        property_id=item.property_id,
        kind=item.kind,
        theme=item.theme,
        platform=item.platform,
        language=target_lang,
        scheduled_at=item.scheduled_at,
        caption=res.caption,
        hashtags=res.hashtags,
        cta=res.cta,
        link=res.link,
        status="draft",
        published_url=None
    )
    return new_item
