from app.adapters.mock import MockPublisher

class TiktokPublisher(MockPublisher):
    def __init__(self):
        super().__init__("tiktok", "tk")
