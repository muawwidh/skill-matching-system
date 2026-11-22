from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CandidatePreference, CandidateWorkEntry, CvDocument, CvSection


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

    def entries_from_cv(self, profile_id: UUID, cv_id: UUID) -> list[CandidateWorkEntry]:
        return list(self.db.scalars(select(CandidateWorkEntry).where(
            CandidateWorkEntry.candidate_profile_id == profile_id, CandidateWorkEntry.source_cv_id == cv_id)))

    def release_cv(self, profile_id: UUID, cv_id: UUID, remove_entries: bool) -> int:
        """Before a CV is deleted: remove the entries taken from it, or keep them without the link.
        Manual entries never have a source CV, so they are never touched. Returns rows affected."""
        entries = self.entries_from_cv(profile_id, cv_id)
        if remove_entries:
            for entry in entries:
                self.db.delete(entry)
        else:
            for entry in entries:
                entry.source_cv_id = None
        self.db.flush()
        return len(entries)

    def work_section_texts(self, profile_id: UUID, section_types: frozenset[str]) -> list[tuple[UUID, str]]:
        return list(self.db.execute(select(CvDocument.id, CvSection.content)
                                    .join(CvDocument, CvDocument.id == CvSection.cv_document_id)
                                    .where(CvDocument.candidate_profile_id == profile_id,
                                           CvDocument.status == "processed",
                                           CvSection.section_type.in_(sorted(section_types)))
                                    .order_by(CvDocument.created_at.desc(), CvSection.start_char)))

    def preference(self, profile_id: UUID) -> CandidatePreference | None:
        return self.db.get(CandidatePreference, profile_id)

    def set_hide_below_experience(self, profile_id: UUID, value: bool) -> CandidatePreference:
        preference = self.preference(profile_id)
        if preference is None:
            preference = CandidatePreference(candidate_profile_id=profile_id)
            self.db.add(preference)
        preference.hide_below_experience = value
        self.db.flush()
        return preference
