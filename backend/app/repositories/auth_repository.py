from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RefreshToken, Role, User


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def get_user_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_or_create_role(self, name: str, description: str = "") -> Role:
        role = self.db.scalar(select(Role).where(Role.name == name))
        if role:
            return role

        role = Role(name=name, description=description)
        self.db.add(role)
        self.db.flush()
        return role

    def create_user(
        self,
        email: str,
        full_name: str,
        hashed_password: str,
        roles: list[Role],
    ) -> User:
        user = User(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hashed_password,
            roles=roles,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def store_refresh_token(self, user_id: UUID, token: str, expires_at: datetime) -> None:
        self.db.add(
            RefreshToken(
                user_id=user_id,
                token_hash=self.hash_token(token),
                expires_at=expires_at,
            )
        )

    def get_active_refresh_token(self, token: str) -> RefreshToken | None:
        token_hash = self.hash_token(token)
        now = datetime.now(timezone.utc)
        return self.db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )

    def revoke_refresh_token(self, token: str) -> bool:
        stored_token = self.get_active_refresh_token(token)
        if not stored_token:
            return False
        stored_token.revoked_at = datetime.now(timezone.utc)
        return True

    @staticmethod
    def hash_token(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()
