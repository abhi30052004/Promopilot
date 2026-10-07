from app.adapters.mock import MockPublisher

class XPublisher(MockPublisher):
    def __init__(self):
        super().__init__("x", "x")
