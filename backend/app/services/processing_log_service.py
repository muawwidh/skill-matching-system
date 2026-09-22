from sqlalchemy.orm import Session

from app.db.models import ProcessingLog
from app.repositories.document_repository import DocumentRepository


class ProcessingLogService:
    def __init__(self, db: Session) -> None:
        self.repository = DocumentRepository(db)

    def list_logs(self, entity_type: str | None = None) -> list[ProcessingLog]:
        return self.repository.list_processing_logs(entity_type=entity_type)
