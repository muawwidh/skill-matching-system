"""Candidate account deletion."""
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.db.models import CandidateProfile, User
from app.repositories.auth_repository import AuthRepository
from app.repositories.document_repository import DocumentRepository

log = logging.getLogger(__name__)


class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.documents = DocumentRepository(db)
        self.auth = AuthRepository(db)

    def delete_my_account(self, user: User, password: str) -> dict[str, int]:
        """Delete a candidate's account and all data derived from it, after a password check.

        Staff accounts (administrator/researcher) are refused: their review
        decisions are attributed to them and they are removed by an administrator.
        """
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The password is incorrect.")
        roles = {role.name for role in user.roles}
        if settings.DEFAULT_CANDIDATE_ROLE not in roles or roles & {settings.ADMIN_ROLE, settings.RESEARCHER_ROLE}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only candidate accounts can be deleted here.")
        try:
            profile = self.db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
            counts = self.documents.delete_candidate_profile_data(profile) if profile else {}
            self.auth.delete_user(user)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        # No identifier is logged: the account no longer exists.
        log.info("Candidate account deleted: %s", {key: value for key, value in counts.items() if value})
        return counts
