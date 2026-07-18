from fastapi import FastAPI

from newsagent.api.routers import admin, me


def create_app() -> FastAPI:
    app = FastAPI(title="NewsAgent API")
    app.include_router(admin.router)
    app.include_router(me.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
