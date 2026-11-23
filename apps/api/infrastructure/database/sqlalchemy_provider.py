from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class SQLAlchemyDatabaseProvider:
    def __init__(self, url: str):
        self.url = self.normalize_url(url)
        connect_args = {"check_same_thread": False} if self.url.startswith("sqlite") else {}
        engine_kwargs = {
            "connect_args": connect_args,
            "pool_pre_ping": True,
        }
        if self.url.startswith("postgresql"):
            engine_kwargs.update({
                "pool_size": 3,
                "max_overflow": 5,
                "pool_timeout": 15,
                "pool_recycle": 280,
            })
        self.engine = create_engine(self.url, **engine_kwargs)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def normalize_url(url: str) -> str:
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            parsed = urlsplit(url)
            if parsed.hostname and ("pooler.supabase.com" not in parsed.hostname) and (
                parsed.hostname.endswith(".supabase.co")
                or parsed.hostname.endswith(".supabase.com")
            ):
                raise RuntimeError(
                    "Use the Supabase transaction pooler URL on Render (port 6543), "
                    "not the direct IPv6 database host on port 5432"
                )
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
        elif url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql") and "supabase." in url:
            parts = urlsplit(url)
            query = dict(parse_qsl(parts.query, keep_blank_values=True))
            query.setdefault("sslmode", "require")
            url = urlunsplit(parts._replace(query=urlencode(query)))
        return url

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
