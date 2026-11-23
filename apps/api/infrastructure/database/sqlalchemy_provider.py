from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class SQLAlchemyDatabaseProvider:
    def __init__(self, url: str):
        self.url = url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_session(self):
        return self.sessions()

    def dispose(self) -> None:
        self.engine.dispose()

    @property
    def sqlite_path(self) -> Path | None:
        if not self.url.startswith("sqlite"):
            return None
        value = self.url.removeprefix("sqlite:///")
        path = Path(value)
        return path if path.is_absolute() else Path.cwd() / path
