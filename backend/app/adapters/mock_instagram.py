from app.adapters.mock import MockPublisher

class InstagramPublisher(MockPublisher):
    def __init__(self):
        super().__init__("instagram", "ig")
