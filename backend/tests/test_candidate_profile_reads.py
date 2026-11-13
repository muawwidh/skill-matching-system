"""The presentation's ownership lookup must never create or commit a profile."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select

from app.db.models import CandidateProfile, User
from app.services.candidate_service import CandidateService
from app.api.dependencies.auth import get_current_user


@pytest.mark.parametrize("exists", [False, True])
def test_profile_lookup_is_read_only(db_session, exists):
    user = User(id=uuid4(), email="profile-read@example.test", full_name="Synthetic", hashed_password="unused")
    db_session.add(user)
    if exists:
        db_session.add(CandidateProfile(user_id=user.id))
    db_session.commit()
    before = list(db_session.scalars(select(CandidateProfile.id)))
    writes = []

    def statement(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() != "SELECT":
            writes.append(statement)

    def committed(session):
        writes.append("COMMIT")

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", statement)
    event.listen(db_session, "after_commit", committed)
    try:
        if exists:
            assert CandidateService(db_session).get_my_profile(user).user_id == user.id
        else:
            with pytest.raises(HTTPException) as error:
                CandidateService(db_session).get_my_profile(user)
            assert error.value.status_code == 404
        assert list(db_session.scalars(select(CandidateProfile.id))) == before
        assert writes == []
    finally:
        event.remove(engine, "before_cursor_execute", statement)
        event.remove(db_session, "after_commit", committed)


@pytest.mark.parametrize("exists", [False, True])
def test_authenticated_profile_get_never_writes(client, db_session, exists):
    user = User(id=uuid4(), email="profile-api@example.test", full_name="Synthetic", hashed_password="unused")
    db_session.add(user)
    if exists:
        db_session.add(CandidateProfile(user_id=user.id))
    db_session.commit()
    client.app.dependency_overrides[get_current_user] = lambda: user
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    def commit(session):
        statements.append("COMMIT")

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    event.listen(db_session, "after_commit", commit)
    try:
        response = client.get("/candidates/me")
        assert response.status_code == (200 if exists else 404)
        assert statements and set(statements) == {"SELECT"}
        if exists:
            assert response.json()["user_id"] == str(user.id)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        event.remove(db_session, "after_commit", commit)
        client.app.dependency_overrides.pop(get_current_user, None)
