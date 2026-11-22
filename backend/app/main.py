from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, candidates, cvs, health, jobs, matches, retrieval, taxonomy
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.WARM_JOB_CACHE_ON_STARTUP:
        from app.retrieval.warmup import start_background_warmup

        # In the background: the server accepts requests at once.
        app.state.warmup_thread = start_background_warmup()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.APP_VERSION,
        description="Transparent skill gap and job matching research platform.",
        lifespan=lifespan,
    )

    if settings.WARM_JOB_CACHE_ON_STARTUP:
        from app.retrieval import warmup

        @app.middleware("http")
        async def pause_warmup_during_requests(request, call_next):
            # The startup warm-up yields to requests.
            warmup.request_started()
            try:
                return await call_next(request)
            finally:
                warmup.request_finished()

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
    app.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
    app.include_router(taxonomy.router, prefix="/taxonomy", tags=["taxonomy"])
    app.include_router(admin.router, prefix="/admin", tags=["administration"])
    return app


app = create_app()
