import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.engine.reflection import Inspector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL)
inspector = Inspector.from_engine(engine)

tables = inspector.get_table_names()
print("Tables in database:")
for table in tables:
    print(f"- {table}")
