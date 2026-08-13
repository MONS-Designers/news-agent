from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from newsagent.api.routers import admin, admin_engagement, admin_taxonomy, auth, me, tracking
from newsagent.config import settings
from newsagent.logging_setup import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="NewsAgent API")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        domain=settings.session_cookie_domain or None,
    )
    # Needed once frontend and backend are split across subdomains (e.g.
    # app.example.com / api.example.com) — same-origin deploys work fine
    # without this, since the browser never treats same-origin requests as
    # cross-site to begin with.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(admin_taxonomy.router)
    app.include_router(admin_engagement.router)
    app.include_router(me.router)
    app.include_router(tracking.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
