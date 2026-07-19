from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from newsagent.api.routers import admin, auth, me
from newsagent.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="NewsAgent API")
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(me.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
