import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import database.models  # noqa: F401
from config import STORAGE_BASE_PATH
from database.models.base import Base

logger = logging.getLogger(__name__)


DATABASE_FILENAME = "box_measurement.sqlite3"


def create_db_session_factory() -> sessionmaker[Session]:
    database_path = Path(STORAGE_BASE_PATH) / DATABASE_FILENAME
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


DbSession: sessionmaker[Session] = create_db_session_factory()
