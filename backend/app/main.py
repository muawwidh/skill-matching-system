from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, candidates, cvs, health, jobs, matches
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.APP_VERSION,
        description="Transparent skill gap and job matching research platform.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["authentication"])
    app.include_router(candidates.router, prefix="/candidates", tags=["candidates"])
    app.include_router(cvs.router, prefix="/cvs", tags=["cvs"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(matches.router, prefix="/matches", tags=["matches"])
    app.include_router(admin.router, prefix="/admin", tags=["administration"])
    return app


app = create_app()
