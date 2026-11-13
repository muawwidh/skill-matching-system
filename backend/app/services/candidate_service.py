from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import CandidateProfile, User
from app.repositories.document_repository import DocumentRepository
from app.schemas.documents import CandidateProfileUpdate


class CandidateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)

    def get_my_profile(self, user: User) -> CandidateProfile:
        profile = self.repository.get_candidate_profile(user.id)
        if profile is None:
            raise HTTPException(404, "Candidate profile not found")
        return profile

    def update_my_profile(self, user: User, payload: CandidateProfileUpdate) -> CandidateProfile:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        profile = self.repository.update_candidate_profile(
            profile=profile,
            headline=payload.headline,
            summary=payload.summary,
            consent_to_process_cv=payload.consent_to_process_cv,
        )
        self.db.commit()
        self.db.refresh(profile)
        return profile
