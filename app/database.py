from typing import Generator
from sqlmodel import Session, SQLModel, create_engine
from app.config import settings

# For SQLite, check_same_thread=False allows FastAPI multi-threading
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency that yields a database session and safely closes it."""
    with Session(engine) as session:
        yield session
