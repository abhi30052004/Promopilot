from abc import ABC, abstractmethod
from typing import Dict, Any
from app.models import ContentItem

class BasePublisher(ABC):
    @abstractmethod
    def publish(self, item: ContentItem) -> Dict[str, Any]:
        """
        Publish the content item.
        Returns a dict with at least:
        - status: "success" or "failed"
        - external_id: string
        - url: string
        - error: Optional string
        - demo: boolean
        """
        pass
