import logging
import os

from fastapi import FastAPI, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from newsagent.api.routers import admin, admin_engagement, admin_taxonomy, auth, me, tracking
from newsagent.config import settings
from newsagent.db import SessionLocal
from newsagent.logging_setup import configure_logging


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    if settings.dev_auth_email:
        # Loud on every boot, not just on use: the failure mode is nobody
        # noticing it is on, so it has to announce itself before it is reached.
        logger.warning(
            "DEV LOGIN IS ENABLED: GET /auth/dev-login signs in as %s with no "
            "Google verification. Unset NEWSAGENT_DEV_AUTH_EMAIL outside local development.",
            settings.dev_auth_email,
        )
    app = FastAPI(title="NewsAgent API")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        domain=settings.session_cookie_domain or None,
    )
    # Needed once frontend and backend are split across subdomains (e.g.
    # app.example.com / api.example.com) - same-origin deploys work fine
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
        return {"status": "ok", "commit": os.environ.get("GIT_SHA", "unknown")}

    @app.get("/health/db")
    def health_db(response: Response) -> dict[str, str]:
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("DB health check failed", exc_info=True)
            response.status_code = 503
            return {"status": "error"}
        return {"status": "ok"}

    return app


app = create_app()
