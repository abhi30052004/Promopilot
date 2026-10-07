from app.adapters.mock import MockPublisher

class FacebookPublisher(MockPublisher):
    def __init__(self):
        super().__init__("facebook", "fb")
