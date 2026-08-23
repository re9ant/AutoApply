import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings
from app.database.models import Base

logger = logging.getLogger(__name__)

# Ensure data directory exists
db_path = settings.resolve_path("data/autoapply.db")
db_path.parent.mkdir(parents=True, exist_ok=True)

# Synchronous SQLite engine for clean local operation
sync_db_url = f"sqlite:///{db_path}"
engine = create_engine(sync_db_url, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")
