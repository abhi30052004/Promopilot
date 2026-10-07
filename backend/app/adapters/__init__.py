from .base import BasePublisher
from .mock_facebook import FacebookPublisher
from .mock_instagram import InstagramPublisher
from .mock_tiktok import TiktokPublisher
from .mock_x import XPublisher
from .mock_linkedin import LinkedInPublisher
from .mock import MockPublisher

# Spec name: until real credentials/providers exist every platform is served by the demo provider.
DemoPublishingProvider = MockPublisher
from .telegram import TelegramPublisher

def get_adapter(platform: str) -> BasePublisher:
    adapters = {
        "facebook": FacebookPublisher,
        "instagram": InstagramPublisher,
        "tiktok": TiktokPublisher,
        "x": XPublisher,
        "linkedin": LinkedInPublisher,
        "telegram": TelegramPublisher
    }
    adapter_cls = adapters.get(platform)
    if not adapter_cls:
        raise ValueError(f"No adapter for platform {platform}")
    return adapter_cls()
