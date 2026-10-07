from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import get_settings

settings = get_settings()

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

pool_kwargs = {}
if not settings.DATABASE_URL.startswith("sqlite"):
    # The database is remote (~0.3s per round trip, ~4s per NEW connection): keep a warm pool,
    # recycle before the server drops idle sockets, and keep TCP alive instead of pinging on
    # every checkout (pre_ping would add a full extra round trip to every request).
    pool_kwargs = dict(pool_size=10, max_overflow=10, pool_recycle=240, pool_pre_ping=False)
    if settings.DATABASE_URL.startswith("postgresql"):
        connect_args.update(keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **pool_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
