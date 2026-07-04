from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_challenges import router as admin_challenges_router
from app.api.auth import router as auth_router
from app.api.challenges import router as challenges_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.posts import router as posts_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.middleware import RequestIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Challenge & Rewards Engine", version="0.1.0")

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(posts_router, prefix="/api")
    app.include_router(events_router, prefix="/api")
    app.include_router(admin_challenges_router, prefix="/api")
    app.include_router(challenges_router, prefix="/api")
    app.include_router(users_router, prefix="/api")

    return app


app = create_app()
