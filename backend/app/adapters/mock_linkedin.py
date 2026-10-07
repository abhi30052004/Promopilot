from app.adapters.mock import MockPublisher


class LinkedInPublisher(MockPublisher):
    """Demo LinkedIn provider (no real LinkedIn API call is made)."""

    def __init__(self):
        super().__init__("linkedin", "li")
