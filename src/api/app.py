from __future__ import annotations

from fastapi import FastAPI

from .router import router

__all__ = ["create_app"]


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Chat API", version="1.0.0")
    app.include_router(router)
    return app
