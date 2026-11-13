"""Synthetic run orchestration checks; SQLite mocks ranking, never source capture."""
import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.base import Base
from app.db.models import (
    CandidateProfileEmbedding, CandidateSkill, CvDocument, ExtractedCandidateTerm,
    Job, JobEmbedding, JobSkill, User,
)
from app.db.models.explainable import (
    JobMatchResult, MatchScoreComponent, MatchingRun, ScoringConfiguration,
    SkillGapAtomicResult, SkillGapResult,
)
from app.db.session import get_db
from app.main import create_app
from app.matching.policy import CANONICAL_CONFIGURATION, POLICY_HASH, POLICY_VERSION
from app.repositories.matching_inputs_repository import snapshot
from app.repositories.matching_runs_repository import MatchingRunsRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import DIMENSION, MODEL_ID, MODEL_REVISION, TEMPLATE_V2
from app.services.matching_inputs_service import MatchingInputsService
from app.services.retrieval_service import RetrievalService
from test_matching_inputs import group_payload, seed, sign_payload


RUN_TABLES = {
    "matching_runs", "job_match_results", "match_score_components", "skill_gap_results",
    "skill_gap_atomic_results",
}


@pytest.fixture(autouse=True)
def forbid_matching_inference(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Matching run creation/read must not instantiate or encode with an embedding model")

    monkeypatch.setattr("app.retrieval.embedder.LocalE5Embedder.__init__", forbidden)
    monkeypatch.setattr("app.retrieval.embedder.LocalE5Embedder.encode", forbidden)


def runs_service(db):
    from app.services.matching_runs_service import MatchingRunsService
    return MatchingRunsService(db)


def seed_runs(db, *, complete=True):
    users, profiles, job, skill = seed(db)
    if db.scalar(select(ScoringConfiguration).where(ScoringConfiguration.version == POLICY_VERSION)) is None:
        db.add(ScoringConfiguration(version=POLICY_VERSION, canonical_json=CANONICAL_CONFIGURATION,
                                   policy_hash=POLICY_HASH, engine_version=POLICY_VERSION))
    profiles[0].consent_to_process_cv = True
    db.add(CandidateSkill(candidate_profile_id=profiles[0].id, raw_text="Python", normalized_text="python",
                          skill_type="skill", review_status="approved", source="manual_review",
                          evidence_sentence="Candidate-confirmed synthetic Python practice"))
    db.commit()
    inputs = MatchingInputsService(db)
    inputs.create_group(users[1], job.id, group_payload(inputs.read_job(job.id), skill))
    if complete:
        inputs.signoff(users[1], job.id, sign_payload(inputs.read_job(job.id)))
    retrieval = RetrievalRepository(db, TEMPLATE_V2)
    vector = [1.0] + [0.0] * (DIMENSION - 1)
    retrieval.upsert(profiles[0].id, "profile", retrieval.profile_input(profiles[0].id), vector)
    retrieval.upsert(job.id, "job", retrieval.job_input(job), vector)
    db.commit()
    return users, profiles, job, skill


def sqlite_retrieval(monkeypatch):
    calls = []

    def jobs(service, user, limit):
        assert service.db.bind.dialect.name == "sqlite", "PostgreSQL must use actual vector retrieval"
        assert service.repository.template_version == TEMPLATE_V2
        assert limit == 20
        calls.append((user.id, limit))
        profile = MatchingRunsRepository(service.db).profile(user.id)
        source = service.repository.profile_embedding(profile.id)
        rows = service.db.scalars(select(JobEmbedding).order_by(JobEmbedding.job_id)).all()
        return [{"rank": index, "job_id": row.job_id, "retrieval_similarity": 1.0,
                 "model_id": MODEL_ID, "model_revision": MODEL_REVISION, "template_version": TEMPLATE_V2,
                 "candidate_input_hash": source.source_hash, "job_input_hash": row.source_hash,
                 "candidate_indexed_at": source.indexed_at, "job_indexed_at": row.indexed_at}
                for index, row in enumerate(rows, 1) if row.status == "ready"][:limit]

    monkeypatch.setattr(RetrievalService, "jobs_for_user", jobs)
    return calls


def add_ready_job(db, reviewer, *, skill_text="Python", job_id=None):
    job = Job(id=job_id or uuid4(), title="Synthetic additional job", description=f"Requires {skill_text}",
              status="processed")
    db.add(job)
    db.flush()
    skill = JobSkill(job_id=job.id, raw_text=skill_text, normalized_text=skill_text.lower(),
                     skill_type="skill", review_status="approved", requirement_type="required")
    db.add(skill)
    db.commit()
    inputs = MatchingInputsService(db)
    inputs.create_group(reviewer, job.id, group_payload(inputs.read_job(job.id), skill))
    inputs.signoff(reviewer, job.id, sign_payload(inputs.read_job(job.id)))
    repo = RetrievalRepository(db, TEMPLATE_V2)
    repo.upsert(job.id, "job", repo.job_input(job), [1.0] + [0.0] * (DIMENSION - 1))
    db.commit()
    return job


def table_snapshot(db, *, exclude=()):
    return {table.name: sorted(json.dumps(dict(row), sort_keys=True, default=str)
                              for row in db.execute(select(table)).mappings())
            for table in Base.metadata.sorted_tables if table.name not in exclude}


def run_rows(db):
    return list(db.scalars(select(MatchingRun).order_by(MatchingRun.created_at, MatchingRun.id)))


def assert_complete(db, run):
    results = list(db.scalars(select(JobMatchResult).where(JobMatchResult.run_id == run.id)))
    assert len(results) == 1
    result = results[0]
    assert result.alignment_fraction == "100/1"
    assert result.alignment_value == Decimal("100.000000")
    assert result.status == "ready" and not result.provisional
    assert result.retrieval_rank == 1 and result.retrieval_similarity == 1
    components = list(db.scalars(select(MatchScoreComponent).where(MatchScoreComponent.result_id == result.id)))
    assert {row.component for row in components} == {"R", "P", "O", "Q"}
    required = next(row for row in components if row.component == "R")
    assert required.value_fraction == "1/1" and required.effective_weight_fraction == "1/1"
    gaps = list(db.scalars(select(SkillGapResult).where(SkillGapResult.result_id == result.id)))
    assert len(gaps) == 1 and gaps[0].status == "Matched" and gaps[0].support_fraction == "1/1"
    atomic = list(db.scalars(select(SkillGapAtomicResult).where(SkillGapAtomicResult.gap_id == gaps[0].id)))
    assert atomic and all(row.support_fraction == "1/1" for row in atomic)
    return result


def test_synthetic_nonnull_score_and_unchanged_source_tables(db_session, monkeypatch):
    users, profiles, job, skill = seed_runs(db_session)
    calls = sqlite_retrieval(monkeypatch)
    before = table_snapshot(db_session, exclude=RUN_TABLES)
    response = runs_service(db_session).create(users[0])
    run, = run_rows(db_session)
    assert_complete(db_session, run)
    assert response["current"] is True
    assert response["readiness"]["score_ready_jobs"] == 1
    assert response["readiness"]["provisional_jobs"] == 0
    assert response["readiness"]["ranking_evaluation_ready"] is False
    assert "retrieval_pool_incomplete" in response["readiness"]["warnings"]
    assert calls and all(call == (users[0].id, 20) for call in calls)
    assert table_snapshot(db_session, exclude=RUN_TABLES) == before


@pytest.mark.parametrize("index", [1, 2])
def test_additive_admin_researcher_candidate_can_create_and_read_only_own_run(db_session, monkeypatch, index):
    users, profiles, _, _ = seed_runs(db_session)
    profiles[index].consent_to_process_cv = True
    db_session.add(CandidateSkill(candidate_profile_id=profiles[index].id, raw_text="Python",
                                  normalized_text="python", skill_type="skill",
                                  review_status="approved", source="manual_review"))
    db_session.commit()
    repo = RetrievalRepository(db_session, TEMPLATE_V2)
    repo.upsert(profiles[index].id, "profile", repo.profile_input(profiles[index].id),
                [1.0] + [0.0] * (DIMENSION - 1))
    db_session.commit()
    sqlite_retrieval(monkeypatch)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: users[index]
    with TestClient(app) as client:
        assert client.post("/matching-runs", json={}).status_code in {200, 201}
        run, = run_rows(db_session)
        assert client.get(f"/matching-runs/{run.id}").status_code == 200
        assert client.get("/matching-runs/current").status_code == 200
        app.dependency_overrides[get_current_user] = lambda: users[0]
        assert client.get(f"/matching-runs/{run.id}").status_code == 404


def test_incomplete_inventory_is_provisional_not_zero(db_session, monkeypatch):
    users, _, _, _ = seed_runs(db_session, complete=False)
    sqlite_retrieval(monkeypatch)
    response = runs_service(db_session).create(users[0])
    result = db_session.scalar(select(JobMatchResult))
    assert result.provisional and result.status == "provisional"
    assert result.alignment_fraction is None and result.alignment_value is None
    assert response["readiness"]["score_ready_jobs"] == 0
    assert response["readiness"]["provisional_jobs"] == 1
    assert response["readiness"]["ranking_evaluation_ready"] is False


def test_exact_alignment_reranks_original_retrieval_order_without_similarity_weight(db_session, monkeypatch):
    users, _, supported, _ = seed_runs(db_session)
    unsupported = add_ready_job(db_session, users[1], skill_text="Java", job_id=UUID(int=1))
    sqlite_retrieval(monkeypatch)
    response = runs_service(db_session).create(users[0])
    assert [row["job_id"] for row in response["results"]] == [supported.id, unsupported.id]
    assert [row["alignment_fraction"] for row in response["results"]] == ["100/1", "0/1"]
    assert [row["original_retrieval_rank"] for row in response["results"]] == [2, 1]
    assert response["retrieval"]["dense_numeric_weight"] == 0


def test_full_twenty_pool_ready_and_twenty_first_job_excluded(db_session, monkeypatch):
    users, _, _, _ = seed_runs(db_session)
    for _ in range(20):
        add_ready_job(db_session, users[1])
    sqlite_retrieval(monkeypatch)
    response = runs_service(db_session).create(users[0])
    assert len(response["results"]) == 20
    assert response["readiness"]["score_ready_jobs"] == 20
    assert response["readiness"]["ranking_evaluation_ready"] is True
    assert response["retrieval"]["eligible_job_count"] == 21
    assert all(row["alignment_fraction"] == "100/1" for row in response["results"])
    assert [row["original_retrieval_rank"] for row in response["results"]] == list(range(1, 21))


def test_missing_candidate_embedding_409_without_fallback_or_writes(db_session, monkeypatch):
    users, profiles, _, _ = seed_runs(db_session)
    db_session.delete(db_session.scalar(select(CandidateProfileEmbedding)))
    db_session.commit()
    before = table_snapshot(db_session)

    def forbidden(*args, **kwargs):
        pytest.fail("A readiness error must not index or use prototype fallback")

    monkeypatch.setattr(RetrievalService, "index_profile", forbidden)
    monkeypatch.setattr(RetrievalService, "index_job", forbidden)
    monkeypatch.setattr("app.services.matching_service.MatchingService.refresh_my_recommendations", forbidden)
    monkeypatch.setattr("app.services.matching_service.MatchingService.list_my_recommendations", forbidden)
    with pytest.raises(HTTPException) as error:
        runs_service(db_session).create(users[0])
    assert error.value.status_code == 409
    assert table_snapshot(db_session) == before


def test_double_create_retires_previous_and_is_fresh_session_deterministic(db_session, monkeypatch):
    users, _, _, _ = seed_runs(db_session)
    sqlite_retrieval(monkeypatch)
    service = runs_service(db_session)
    service.create(users[0])
    first, = run_rows(db_session)
    first_id, user_id = first.id, users[0].id
    first_result = snapshot(assert_complete(db_session, first))
    service.create(users[0])
    db_session.expire_all()
    rows = run_rows(db_session)
    assert len(rows) == 2 and sum(row.is_current for row in rows) == 1
    old = db_session.get(MatchingRun, first_id)
    new = next(row for row in rows if row.is_current)
    assert old.status == "historical" and not old.is_current
    assert old.input_fingerprint == new.input_fingerprint
    assert snapshot(db_session.get(JobMatchResult, first_result["id"])) == first_result
    new_result = assert_complete(db_session, new)
    for key in ("alignment_fraction", "alignment_value", "retrieval_rank", "retrieval_similarity", "job_fingerprint", "input_fingerprint"):
        assert getattr(new_result, key) == first_result[key]
    with Session(db_session.bind) as fresh:
        service = runs_service(fresh)
        user = fresh.get(User, user_id)
        assert service.current(user) == service.read(user, new.id)
        assert service.read(user, first_id)["current"] is False


def test_finish_failure_rolls_back_retirement_and_all_results(db_session, monkeypatch):
    users, _, _, _ = seed_runs(db_session)
    sqlite_retrieval(monkeypatch)
    runs_service(db_session).create(users[0])
    before = table_snapshot(db_session)

    def fail(repo):
        repo.db.flush()
        raise RuntimeError("injected finish failure")

    monkeypatch.setattr(MatchingRunsRepository, "finish", fail)
    with pytest.raises(RuntimeError, match="injected finish failure"):
        runs_service(db_session).create(users[0])
    assert table_snapshot(db_session) == before
    with Session(db_session.bind) as fresh:
        assert table_snapshot(fresh) == before


@pytest.mark.parametrize("mutation", ["candidate", "job", "vector", "inventory"])
def test_every_read_rechecks_fingerprints_and_hides_stale_scores(db_session, monkeypatch, mutation):
    users, _, job, skill = seed_runs(db_session)
    sqlite_retrieval(monkeypatch)
    service = runs_service(db_session)
    service.create(users[0])
    run, = run_rows(db_session)
    if mutation == "candidate":
        db_session.scalar(select(CandidateSkill)).review_status = "rejected"
    elif mutation == "job":
        job.description = "Changed synthetic source, bypassing invalidation service"
    elif mutation == "vector":
        db_session.scalar(select(JobEmbedding)).embedding = [0.0, 1.0] + [0.0] * (DIMENSION - 2)
    else:
        from app.db.models.explainable import JobInventoryReview
        db_session.scalar(select(JobInventoryReview)).inventory_complete = False
    db_session.commit()
    before = table_snapshot(db_session)
    for response in (service.read(users[0], run.id), service.current(users[0])):
        assert response["current"] is False and response["status"] == "stale"
        assert response["readiness"]["ranking_evaluation_ready"] is False
        assert response["results"]
        assert response["results"][0]["alignment_score"] is None
        assert response["results"][0]["recorded_alignment_fraction"] == "100/1"
    assert table_snapshot(db_session) == before


def test_run_api_auth_ownership_strict_body_and_get_no_writes(db_session, monkeypatch):
    users, _, _, _ = seed_runs(db_session)
    sqlite_retrieval(monkeypatch)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        for method, path, kwargs in [("post", "/matching-runs", {"json": {}}),
                                     ("get", "/matching-runs/current", {}),
                                     ("get", f"/matching-runs/{uuid4()}", {})]:
            assert getattr(client, method)(path, **kwargs).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: users[0]
        for payload in ({"limit": 1}, {"user_id": str(users[3].id)}, {"policy": POLICY_VERSION},
                        {"score": 100}, {"force": True}):
            assert client.post("/matching-runs", json=payload).status_code == 422
        created = client.post("/matching-runs", json={})
        assert created.status_code in {200, 201}
        run, = run_rows(db_session)
        path = f"/matching-runs/{run.id}"
        statements = []

        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement.lstrip().split(None, 1)[0].upper())

        before = table_snapshot(db_session)
        event.listen(db_session.bind, "before_cursor_execute", record)
        try:
            assert client.get(path).status_code == 200
            assert client.get("/matching-runs/current").status_code == 200
            assert client.get(f"/matching-runs/{uuid4()}").status_code == 404
            for user in users[1:]:
                app.dependency_overrides[get_current_user] = lambda: user
                assert client.get(path).status_code == 404
            assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "TRUNCATE"}
            users[1].roles = [role for role in users[1].roles if role.name != "candidate"]
            db_session.commit()
            statements.clear()
            app.dependency_overrides[get_current_user] = lambda: users[1]
            assert client.get(path).status_code == 403
            assert client.get("/matching-runs/current").status_code == 403
            assert client.post("/matching-runs", json={}).status_code == 403
        finally:
            event.remove(db_session.bind, "before_cursor_execute", record)
        assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "TRUNCATE"}
        # Role setup is the only deliberate write in this block.
        after = table_snapshot(db_session)
        assert {k: v for k, v in after.items() if k != "user_roles"} == {
            k: v for k, v in before.items() if k != "user_roles"}


def test_get_reports_live_missing_universe_count_without_rewriting_recorded_count(db_session, monkeypatch):
    users, _, _, _ = seed_runs(db_session)
    sqlite_retrieval(monkeypatch)
    runs_service(db_session).create(users[0])
    run, = run_rows(db_session)
    assert run.stale_missing_job_count == 0
    db_session.add(Job(title="New unindexed synthetic job", description="Python", status="processed"))
    db_session.commit()
    before = table_snapshot(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: users[0]
    with TestClient(app) as client:
        for path in (f"/matching-runs/{run.id}", "/matching-runs/current"):
            response = client.get(path)
            assert response.status_code == 200
            body = response.json()
            assert body["current"] is False and body["status"] == "stale"
            assert "eligible_universe_incomplete" in body["readiness"]["warnings"]
            assert body["retrieval"]["stale_missing_job_count"] == 1
            assert body["retrieval"]["missing_job_embeddings"] == 1
            assert body["retrieval"]["recorded_stale_missing_job_count"] == 0
            assert body["results"][0]["alignment_score"] is None
            assert body["results"][0]["recorded_alignment_fraction"] == "100/1"
    assert table_snapshot(db_session) == before


@pytest.mark.parametrize("canonical", ["{", "{}", CANONICAL_CONFIGURATION.replace('"dense_numeric_weight":0', '"dense_numeric_weight":1')])
def test_loaded_policy_with_same_hash_but_invalid_configuration_rejected(db_session, monkeypatch, canonical):
    users, _, _, _ = seed_runs(db_session)
    sqlite_retrieval(monkeypatch)
    service = runs_service(db_session)
    service.create(users[0])
    run, = run_rows(db_session)
    policy = db_session.scalar(select(ScoringConfiguration))
    policy.canonical_json = canonical
    db_session.commit()
    assert policy.policy_hash == POLICY_HASH and run.policy_fingerprint == POLICY_HASH
    before = table_snapshot(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: users[0]
    with TestClient(app) as client:
        assert client.get(f"/matching-runs/{run.id}").status_code == 409
        assert client.get("/matching-runs/current").status_code == 409
        assert client.post("/matching-runs", json={}).status_code == 409
    assert table_snapshot(db_session) == before


def test_get_exposes_bounded_reviewed_evidence_not_raw_cv_or_foreign_candidate_data(db_session, monkeypatch):
    users, profiles, _, skill = seed_runs(db_session)
    raw_cv = "PRIVATE_WHOLE_CV_NOT_AN_EXPLANATION_" * 1000
    cv = CvDocument(candidate_profile_id=profiles[0].id, content_type="text/plain", source="paste",
                    status="processed", raw_text=raw_cv, cleaned_text=raw_cv)
    db_session.add(cv)
    db_session.flush()
    candidate_skill = db_session.scalar(select(CandidateSkill))
    term = ExtractedCandidateTerm(cv_document_id=cv.id, raw_text="Python", normalized_text="python",
                                  term_type="skill", extraction_method="synthetic_test",
                                  review_status="approved", evidence_sentence=candidate_skill.evidence_sentence)
    db_session.add(term)
    db_session.flush()
    candidate_skill.extracted_term_id = term.id
    db_session.commit()
    repo = RetrievalRepository(db_session, TEMPLATE_V2)
    repo.upsert(profiles[0].id, "profile", repo.profile_input(profiles[0].id),
                [1.0] + [0.0] * (DIMENSION - 1))
    db_session.commit()
    sqlite_retrieval(monkeypatch)
    runs_service(db_session).create(users[0])
    run, = run_rows(db_session)
    before = table_snapshot(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: users[0]
    with TestClient(app) as client:
        for path in (f"/matching-runs/{run.id}", "/matching-runs/current"):
            response = client.get(path)
            assert response.status_code == 200
            body = response.json()
            result = body["results"][0]
            gap, = result["gaps"]
            evidence = gap["evidence"]
            candidate, = evidence["candidate_confirmed_evidence"]
            requirement, = evidence["reviewed_requirements"]
            assert candidate["id"] == str(candidate_skill.id)
            assert candidate["extracted_term_id"] == str(term.id)
            assert gap["atomic_assessments"][0]["reason_parameters"]["candidate_extracted_term_id"] == str(term.id)
            # Gap summaries reference the single source excerpt instead of
            # copying its sentence into every comparison/group snapshot.
            assert "evidence_sentence" not in candidate
            anchor = next(x for x in gap["atomic_assessments"] if x["id"] == candidate["anchor_atomic_id"])
            assert anchor["reason_parameters"]["candidate_evidence"]["evidence_sentence"] == "Candidate-confirmed synthetic Python practice"
            assert requirement["id"] == str(skill.id)
            review = evidence["group_review"]
            assert review["id"] == gap["group_id"]
            assert review["operator"] == "SINGLE" and review["classification"] == "required"
            assert review["reviewer_pseudonym_snapshot"] and review["reviewer_role_snapshot"]
            assert review["reviewed_at"] and len(review["source_fingerprint"]) == 64
            inventory = result["reason_parameters"]["inventory_review"]
            assert inventory["review_status"] == "approved" and inventory["inventory_complete"] is True
            assert len(json.dumps(evidence).encode()) <= 16384
            assert "PRIVATE_WHOLE_CV_NOT_AN_EXPLANATION_" not in response.text
            for user in users:
                assert user.email not in response.text
            assert "hashed_password" not in response.text and "cleaned_text" not in response.text
        for user in users[1:]:
            app.dependency_overrides[get_current_user] = lambda: user
            response = client.get(f"/matching-runs/{run.id}")
            assert response.status_code == 404
            assert "candidate_confirmed_evidence" not in response.text
    assert table_snapshot(db_session) == before
