from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import TokenPair, UserCreate, UserLogin


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AuthRepository(db)

    def register(self, payload: UserCreate) -> tuple[User, TokenPair]:
        if self.repository.get_user_by_email(payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        role = self.repository.get_or_create_role(
            settings.DEFAULT_CANDIDATE_ROLE,
            "Candidate using the recommendation workflow.",
        )
        user = self.repository.create_user(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            roles=[role],
        )
        tokens = self._issue_tokens(user)
        self.db.commit()
        self.db.refresh(user)
        return user, tokens

    def login(self, payload: UserLogin) -> tuple[User, TokenPair]:
        user = self.repository.get_user_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        tokens = self._issue_tokens(user)
        self.db.commit()
        return user, tokens

    def refresh(self, refresh_token: str) -> TokenPair:
        payload = self._decode_refresh(refresh_token)
        stored_token = self.repository.get_active_refresh_token(refresh_token)
        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired.",
            )

        user = self.repository.get_user_by_id(UUID(payload["sub"]))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

        self.repository.revoke_refresh_token(refresh_token)
        tokens = self._issue_tokens(user)
        self.db.commit()
        return tokens

    def logout(self, refresh_token: str) -> None:
        self.repository.revoke_refresh_token(refresh_token)
        self.db.commit()

    def get_user_from_access_token(self, token: str) -> User:
        try:
            payload = decode_token(token, expected_type="access")
            user_id = UUID(payload["sub"])
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
            ) from None

        user = self.repository.get_user_by_id(user_id)
        if not user or user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is not active.",
            )
        return user

    def _issue_tokens(self, user: User) -> TokenPair:
        roles = [role.name for role in user.roles]
        access_token = create_access_token(str(user.id), roles)
        refresh_token, expires_at = create_refresh_token(str(user.id))
        self.repository.store_refresh_token(user.id, refresh_token, expires_at)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    @staticmethod
    def _decode_refresh(refresh_token: str) -> dict:
        try:
            return decode_token(refresh_token, expected_type="refresh")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired.",
            ) from None
