from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CandidateWorkEntry, CvDocument, CvSection


class WorkEntryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_entries(self, profile_id: UUID) -> list[CandidateWorkEntry]:
        return list(self.db.scalars(select(CandidateWorkEntry).where(
            CandidateWorkEntry.candidate_profile_id == profile_id).order_by(
            CandidateWorkEntry.start_month.desc(), CandidateWorkEntry.id)))

    def get_entry(self, profile_id: UUID, entry_id: UUID) -> CandidateWorkEntry | None:
        return self.db.scalar(select(CandidateWorkEntry).where(
            CandidateWorkEntry.candidate_profile_id == profile_id, CandidateWorkEntry.id == entry_id))

    def count_entries(self, profile_id: UUID) -> int:
        return len(self.list_entries(profile_id))

    def add(self, entry: CandidateWorkEntry) -> CandidateWorkEntry:
        self.db.add(entry)
        self.db.flush()
        return entry

    def delete(self, entry: CandidateWorkEntry) -> None:
        self.db.delete(entry)
        self.db.flush()

    def work_section_texts(self, profile_id: UUID, section_types: frozenset[str]) -> list[str]:
        return list(self.db.scalars(select(CvSection.content).join(CvDocument, CvDocument.id == CvSection.cv_document_id)
                                    .where(CvDocument.candidate_profile_id == profile_id,
                                           CvDocument.status == "processed",
                                           CvSection.section_type.in_(sorted(section_types)))
                                    .order_by(CvDocument.created_at.desc(), CvSection.start_char)))
