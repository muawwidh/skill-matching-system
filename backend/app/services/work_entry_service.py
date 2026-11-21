"""Candidate work entries (D060): self-entered, optionally pre-filled from CV dates."""
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import CandidateWorkEntry, User
from app.matching.experience import merged_months
from app.matching.work_history import WORK_SECTIONS, detect_entries
from app.repositories.document_repository import DocumentRepository
from app.repositories.work_entry_repository import WorkEntryRepository
from app.schemas.experience import WorkEntryWrite, date_to_month, month_to_date
from app.taxonomy.occupations import occupation_catalog

MAX_ENTRIES = 50


def current_month(today: date | None = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    return date(today.year, today.month, 1)


class WorkEntryService:
    def __init__(self, db: Session, today: date | None = None) -> None:
        self.db = db
        self.repository = WorkEntryRepository(db)
        self.documents = DocumentRepository(db)
        self.today = today or datetime.now(timezone.utc).date()

    def _profile_id(self, user: User) -> UUID:
        return self.documents.get_or_create_candidate_profile(user.id).id

    def _read(self, entry: CandidateWorkEntry, catalog) -> dict:
        end = entry.end_month or current_month(self.today)
        return {"id": entry.id, "title": entry.title, "start_month": date_to_month(entry.start_month),
                "end_month": date_to_month(entry.end_month), "source": entry.source,
                "months": merged_months([(entry.start_month, end)]),
                "occupation": catalog.describe(entry.occupation_concept_id)}

    def list_entries(self, user: User) -> list[dict]:
        catalog = occupation_catalog(self.db)
        entries = self.repository.list_entries(self._profile_id(user))
        self.db.commit()
        return [self._read(entry, catalog) for entry in entries]

    def _apply(self, entry: CandidateWorkEntry, payload: WorkEntryWrite) -> None:
        start = month_to_date(payload.start_month)
        end = month_to_date(payload.end_month) if payload.end_month else None
        limit = current_month(self.today)
        if start > limit or (end and end > limit):
            raise HTTPException(status_code=422, detail="Months cannot be in the future.")
        if payload.occupation_concept_id and not occupation_catalog(self.db).is_occupation(payload.occupation_concept_id):
            raise HTTPException(status_code=422, detail="Choose an ESCO occupation from the suggestions.")
        entry.title, entry.start_month, entry.end_month = payload.title, start, end
        entry.occupation_concept_id, entry.source = payload.occupation_concept_id, payload.source

    def create(self, user: User, payload: WorkEntryWrite) -> dict:
        profile_id = self._profile_id(user)
        if self.repository.count_entries(profile_id) >= MAX_ENTRIES:
            raise HTTPException(status_code=422, detail=f"At most {MAX_ENTRIES} work entries.")
        entry = CandidateWorkEntry(candidate_profile_id=profile_id)
        self._apply(entry, payload)
        self.repository.add(entry)
        self.db.commit()
        return self._read(entry, occupation_catalog(self.db))

    def update(self, user: User, entry_id: UUID, payload: WorkEntryWrite) -> dict:
        entry = self._own(user, entry_id)
        self._apply(entry, payload)
        self.db.commit()
        return self._read(entry, occupation_catalog(self.db))

    def delete(self, user: User, entry_id: UUID) -> None:
        self.repository.delete(self._own(user, entry_id))
        self.db.commit()

    def _own(self, user: User, entry_id: UUID) -> CandidateWorkEntry:
        entry = self.repository.get_entry(self._profile_id(user), entry_id)
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work entry not found.")
        return entry

    def occupation_suggestions(self, title: str, limit: int = 5) -> list[dict]:
        """Top ESCO occupations for a title (occupation-only linking with title clean-up)."""
        catalog = occupation_catalog(self.db)
        return [{**catalog.describe(match.concept_id), "confidence": match.confidence}
                for match in catalog.suggest(title[:255], limit)]

    def detected(self, user: User) -> list[dict]:
        """Dated entries found in the candidate's processed CVs that are not entered yet."""
        profile_id = self._profile_id(user)
        stored = {(e.start_month, e.end_month) for e in self.repository.list_entries(profile_id)}
        found: dict[tuple, dict] = {}
        for text in self.repository.work_section_texts(profile_id, WORK_SECTIONS):
            for item in detect_entries(text, self.today):
                key = (item.start_month, item.end_month)
                if key in stored or key in found:
                    continue
                found[key] = {"title": item.title, "start_month": date_to_month(item.start_month),
                              "end_month": date_to_month(item.end_month), "month_precision": item.month_precision}
        self.db.commit()
        return sorted(found.values(), key=lambda e: e["start_month"], reverse=True)
