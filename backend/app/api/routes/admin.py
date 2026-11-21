from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.core.config import settings
from app.db.session import get_db
from app.schemas.documents import ProcessingLogRead, SystemOverviewRead
from app.schemas.taxonomy import TaxonomyLinkCandidateRead
from app.services.processing_log_service import ProcessingLogService, SystemOverviewService
from app.services.taxonomy_service import TaxonomyService

router = APIRouter(
    dependencies=[Depends(require_roles(settings.ADMIN_ROLE, settings.RESEARCHER_ROLE))]
)


@router.get("/logs", response_model=list[ProcessingLogRead])
def list_processing_logs(
    entity_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProcessingLogRead]:
    return ProcessingLogService(db).list_logs(entity_type=entity_type)


@router.get("/mappings/review", response_model=list[TaxonomyLinkCandidateRead])
def list_taxonomy_mappings_for_review(
    db: Session = Depends(get_db),
) -> list[TaxonomyLinkCandidateRead]:
    return TaxonomyService(db).pending_links()


@router.get(
    "/overview",
    response_model=SystemOverviewRead,
    # Narrower than the router guard: administrators only, not researchers.
    dependencies=[Depends(require_roles(settings.ADMIN_ROLE))],
)
def system_overview(db: Session = Depends(get_db)) -> SystemOverviewRead:
    return SystemOverviewService(db).overview()


def _run_import_in_background() -> None:
    from app.db.session import SessionLocal
    from app.job_sources.http import HttpJsonClient
    from app.job_sources.registry import build_adapters
    from app.services.job_import_service import ImportAlreadyRunning, JobImportService

    client = HttpJsonClient(settings.JOB_SOURCE_USER_AGENT, settings.JOB_SOURCE_MIN_INTERVAL_SECONDS)
    with SessionLocal() as db:
        try:
            JobImportService(db, build_adapters(settings), client).run()
        except ImportAlreadyRunning:
            pass


@router.get("/job-import", dependencies=[Depends(require_roles(settings.ADMIN_ROLE))])
def job_import_status(db: Session = Depends(get_db)) -> dict:
    """Whether a live job import is running, and the latest runs (D055)."""
    from app.services.job_import_service import is_import_running, latest_import_runs

    return {"running": is_import_running(), "runs": latest_import_runs(db)}


@router.post("/job-import", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_roles(settings.ADMIN_ROLE))])
def start_job_import(background_tasks: BackgroundTasks) -> dict:
    """Start a live job import in the background (admin only)."""
    from app.services.job_import_service import is_import_running

    if is_import_running():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A job import is already running.")
    background_tasks.add_task(_run_import_in_background)
    return {"started": True}
