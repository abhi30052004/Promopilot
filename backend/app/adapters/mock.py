import os
import time
import random
import uuid
from typing import Dict, Any
from app.models import ContentItem
from app.adapters.base import BasePublisher

class MockPublisher(BasePublisher):
    def __init__(self, platform_name: str, prefix: str):
        self.platform_name = platform_name
        self.prefix = prefix
        self.failure_rate = float(os.environ.get("MOCK_FAILURE_RATE", "0"))

    def publish(self, item: ContentItem) -> Dict[str, Any]:
        # 0.5-1.5s delay
        time.sleep(random.uniform(0.5, 1.5))
        
        if random.random() < self.failure_rate:
            return {
                "status": "failed",
                "error": f"Simulated random failure for {self.platform_name}",
                "demo": True
            }
            
        ext_id = f"demo-{self.prefix}-{uuid.uuid4().hex[:8]}"
        return {
            "status": "success",
            "external_id": ext_id,
            "url": f"http://localhost:5173/feeds/{self.platform_name}/{ext_id}",
            "demo": True
        }
