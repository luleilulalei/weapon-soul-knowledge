from __future__ import annotations

import logging

from fastapi import FastAPI

from usaki_server.api.device import router as device_router
from usaki_server.api.spirit import router as spirit_router
from usaki_server.api.motion import router as motion_router
from usaki_server.api.voice_input import router as voice_router
from usaki_server.audio.provider_factory import create_voice_providers
from usaki_server.config import get_settings
from usaki_server.global_providers import set_voice_providers
from usaki_server.storage.sqlite import init_database

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.server_name)

    @app.on_event("startup")
    async def startup() -> None:
        init_database()
        providers = create_voice_providers(settings)
        set_voice_providers(providers)

    app.include_router(device_router, prefix="/api/v1/device", tags=["device"])
    if settings.device_profile == "usaki":
        app.include_router(motion_router, prefix="/api/v1/motion", tags=["motion"])
    app.include_router(spirit_router, prefix="/api/v1/spirit", tags=["spirit"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "profile": settings.device_profile, "protocol": "spirit.v1"}
    app.include_router(voice_router, prefix="/api/v1/voice", tags=["voice"])
    return app


app = create_app()
