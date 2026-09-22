from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.core.config import settings
from app.db.session import get_db
from app.schemas.documents import ProcessingLogRead
from app.services.processing_log_service import ProcessingLogService

router = APIRouter(
    dependencies=[Depends(require_roles(settings.ADMIN_ROLE, settings.RESEARCHER_ROLE))]
)


@router.get("/logs", response_model=list[ProcessingLogRead])
def list_processing_logs(
    entity_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProcessingLogRead]:
    return ProcessingLogService(db).list_logs(entity_type=entity_type)
