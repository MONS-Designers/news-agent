from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from newsagent.api.routers import admin, admin_taxonomy, auth, me, tracking
from newsagent.config import settings
from newsagent.logging_setup import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="NewsAgent API")
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(admin_taxonomy.router)
    app.include_router(me.router)
    app.include_router(tracking.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
