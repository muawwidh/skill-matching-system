import argparse

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Role, User
from app.db.session import SessionLocal


ALLOWED_ROLES = {settings.DEFAULT_CANDIDATE_ROLE, settings.ADMIN_ROLE, settings.RESEARCHER_ROLE}


def grant_role(email: str, role_name: str) -> None:
    if role_name not in ALLOWED_ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(ALLOWED_ROLES))}")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.casefold()))
        if not user:
            raise ValueError(f"No user exists with email {email}.")
        role = db.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name, description=f"{role_name.title()} application access.")
            db.add(role)
            db.flush()
        if role not in user.roles:
            user.roles.append(role)
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant an application role to an existing user.")
    parser.add_argument("email")
    parser.add_argument("role", choices=sorted(ALLOWED_ROLES))
    args = parser.parse_args()
    grant_role(args.email, args.role)
    print(f"Granted {args.role} to {args.email.casefold()}.")


if __name__ == "__main__":
    main()
