import os
import httpx
from typing import Dict, Any
from app.models import ContentItem
from app.adapters.mock import MockPublisher
from app.config import get_settings

class TelegramPublisher(MockPublisher):
    def __init__(self):
        super().__init__("telegram", "tg")
        self.settings = get_settings()

    def publish(self, item: ContentItem) -> Dict[str, Any]:
        token = self.settings.TELEGRAM_BOT_TOKEN
        chat_id = self.settings.TELEGRAM_CHAT_ID
        
        if not token or not chat_id:
            return super().publish(item)
            
        text = f"{item.caption}\n\n{item.cta}\n{item.link}"
        if item.hashtags:
            text += f"\n\n{item.hashtags}"
            
        try:
            url = f"https://api.telegram.org/bot{token}/"
            if item.media and item.media.storage_url:
                # Telegram accepts an HTTPS URL directly; this also works when media
                # lives in persistent object storage behind PromoPilot's token route.
                resp = httpx.post(
                    url + "sendPhoto",
                    data={"chat_id": chat_id, "caption": text, "photo": item.media.public_url},
                    timeout=30.0,
                )
            elif item.image_path:
                abs_path = os.path.join(self.settings.MEDIA_DIR, item.image_path.strip('/'))
                if os.path.exists(abs_path):
                    with open(abs_path, 'rb') as f:
                        resp = httpx.post(
                            url + "sendPhoto",
                            data={"chat_id": chat_id, "caption": text},
                            files={"photo": f},
                            timeout=15.0
                        )
                else:
                    resp = httpx.post(url + "sendMessage", json={"chat_id": chat_id, "text": text}, timeout=15.0)
            else:
                resp = httpx.post(url + "sendMessage", json={"chat_id": chat_id, "text": text}, timeout=15.0)
                
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                return {"status": "failed", "error": data.get("description", "Unknown TG error"), "demo": False}
                
            msg_id = data["result"]["message_id"]
            chat_username = data["result"]["chat"].get("username")
            post_url = f"https://t.me/{chat_username}/{msg_id}" if chat_username else "https://t.me/c/{}/{}".format(str(chat_id).replace('-100',''), msg_id)
            
            return {
                "status": "success",
                "external_id": str(msg_id),
                "url": post_url,
                "demo": False
            }
        except Exception as e:
            return {"status": "failed", "error": str(e), "demo": False}
