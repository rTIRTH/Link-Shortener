"""Application factory: create_app() builds a fresh, fully configured app."""
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import make_session_factory
from .deps import NotAuthenticated
from .routers import admin, auth, dashboard, redirect
from .templating import BASE_DIR, render


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Link Shortener", version="1.0.0")
    app.state.session_factory = make_session_factory(database_url or settings.database_url)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site="lax",
        https_only=settings.https_only,
        max_age=14 * 24 * 3600,
    )
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.exception_handler(NotAuthenticated)
    async def _login_redirect(request: Request, exc: NotAuthenticated):
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return render(request, "error.html", status_code=exc.status_code,
                      code=exc.status_code, message=exc.detail)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    # Blueprints (called "routers" in FastAPI). The redirect router goes LAST
    # because /{username}/{slug} would otherwise swallow other two-part URLs.
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(admin.router)
    app.include_router(redirect.router)
    return app
