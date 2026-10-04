"""All settings come from environment variables (see .env.example)."""
import os


def _normalize_db_url(url: str) -> str:
    # Render/Heroku give "postgres://..." or "postgresql://...".
    # SQLAlchemy needs to know which driver to use.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class Settings:
    def __init__(self) -> None:
        self.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
        self.database_url = _normalize_db_url(
            os.getenv("DATABASE_URL", "sqlite:///./link_shortener.db")
        )
        self.redis_url = os.getenv("REDIS_URL", "")  # empty = run without cache
        self.base_url = os.getenv("BASE_URL", "").rstrip("/")
        self.https_only = os.getenv("HTTPS_ONLY", "false").lower() == "true"
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))
        # Comma-separated usernames allowed to open /admin, e.g. "r_tirth,alice"
        self.admin_usernames = {
            u.strip().lower() for u in os.getenv("ADMIN_USERNAMES", "").split(",") if u.strip()
        }


settings = Settings()
