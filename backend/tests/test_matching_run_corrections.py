"""Checkpoint 2 acceptance corrections; synthetic evidence only."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.api.dependencies.auth import get_current_user
from app.db.models import CandidateSkill, Job, JobSkill
from app.db.models.explainable import JobMatchResult, SkillGapResult, SkillGapAtomicResult
from app.db.session import get_db
from app.main import create_app
from app.matching.policy import decimal_value, fingerprint
from app.repositories.matching_runs_repository import MatchingRunsRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import TEMPLATE_V2
from app.schemas.matching_inputs import GroupInput
from app.services.matching_inputs_service import MatchingInputsService
from app.services.matching_runs_service import MatchingRunsService, SnapshotLimitError, result_order_key
from test_matching_inputs import group_payload, sign_payload
from test_matching_runs import seed_runs, sqlite_retrieval, table_snapshot


def test_critical_q_is_422_at_request_and_service_boundaries(db_session):
    users, _, job, skill = seed_runs(db_session)
    payload = group_payload(MatchingInputsService(db_session).read_job(job.id), skill)
    invalid = {**payload.model_dump(mode="json"), "component": "Q", "critical": True}
    with pytest.raises(ValueError, match="required-skill R"):
        GroupInput(**invalid)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: users[1]
    before = table_snapshot(db_session)
    with TestClient(app) as client:
        assert client.post(f"/matching-inputs/jobs/{job.id}/groups", json=invalid).status_code == 422
    with pytest.raises(HTTPException) as error:
        MatchingInputsService(db_session).create_group(users[1], job.id, GroupInput.model_construct(**invalid))
    assert error.value.status_code == 422
    assert table_snapshot(db_session) == before


def test_signoff_rejects_critical_q_even_with_valid_required_group(db_session):
    users, _, job, _ = seed_runs(db_session)
    state = deepcopy(MatchingInputsService(db_session).read_job(job.id))
    state["groups"].append({**state["groups"][0], "id": uuid4(), "component": "Q", "critical": True})
    with pytest.raises(HTTPException, match="required-skill R"):
        MatchingInputsService.validate_inventory(state, sign_payload(state))


def two_jobs(db):
    users, profiles, job, skill = seed_runs(db)
    second = Job(title="Second synthetic role", description="Python", cleaned_description="Python", status="processed")
    db.add(second); db.flush()
    second_skill = JobSkill(job_id=second.id, raw_text="Python", normalized_text="python", skill_type="skill",
                            requirement_type="required", review_status="approved")
    db.add(second_skill); db.commit()
    inputs = MatchingInputsService(db)
    inputs.create_group(users[1], second.id, group_payload(inputs.read_job(second.id), second_skill))
    inputs.signoff(users[1], second.id, sign_payload(inputs.read_job(second.id)))
    repo = RetrievalRepository(db, TEMPLATE_V2)
    repo.upsert(second.id, "job", repo.job_input(second), [1.] + [0.] * 383); db.commit()
    return users, profiles, job, second


def inconsistent_capture(monkeypatch, job_id):
    original = MatchingRunsRepository.capture
    def capture(repo, profile):
        captured = original(repo, profile)
        # Model a known bad legacy input that the new database CHECK forbids.
        state = deepcopy(captured["jobs"][str(job_id)])
        state["groups"][0].update(component="Q", critical=True)
        captured["jobs"][str(job_id)] = state
        return captured
    monkeypatch.setattr(MatchingRunsRepository, "capture", capture)


def test_inconsistent_job_is_provisional_and_other_job_still_scores(db_session, monkeypatch):
    users, _, bad, good = two_jobs(db_session)
    sqlite_retrieval(monkeypatch); inconsistent_capture(monkeypatch, bad.id)
    response = MatchingRunsService(db_session).create(users[0])
    results = {x["job_id"]: x for x in response["results"]}
    assert results[bad.id]["alignment_fraction"] is None
    assert results[bad.id]["reason_code"] == "invalid_critical_group"
    assert "invalid_critical_group" in results[bad.id]["reason_parameters"]["readiness_reasons"]
    reference = results[bad.id]["reason_parameters"]["consistency_reference"]
    assert reference["component"] == "Q" and UUID(reference["group_id"])
    assert results[good.id]["alignment_fraction"] == "100/1"
    assert response["readiness"]["score_ready_jobs"] == response["readiness"]["provisional_jobs"] == 1


@pytest.mark.parametrize("exception", [ValueError("engine programming error"), KeyError("implementation bug")])
def test_unexpected_engine_errors_are_not_swallowed(db_session, monkeypatch, exception):
    users, _, _, _ = seed_runs(db_session); sqlite_retrieval(monkeypatch)
    before = table_snapshot(db_session)
    def fail(*args): raise exception
    monkeypatch.setattr("app.services.matching_runs_service.assess_inputs", fail)
    with pytest.raises(type(exception)):
        MatchingRunsService(db_session).create(users[0])
    assert table_snapshot(db_session) == before


def large_inputs(db, *, grouped=False):
    users, profiles, job, skill = seed_runs(db)
    sentence = "Candidate-confirmed practice, not independently verified. " * 200
    first = db.scalar(select(CandidateSkill)); first.evidence_sentence = sentence
    for n in range(59):
        db.add(CandidateSkill(candidate_profile_id=profiles[0].id, raw_text=f"Capability {n}", normalized_text=f"capability {n}",
            skill_type="skill", review_status="approved", source="manual_review", evidence_sentence=sentence))
    if not grouped:
        skill.requirement_type = "unknown"
    for n in range(20 if grouped else 19):
        db.add(JobSkill(job_id=job.id, raw_text=f"Requirement {n}", normalized_text=f"requirement {n}", skill_type="skill",
            requirement_type="required" if grouped else "unknown", review_status="approved", evidence_sentence="Source duty. " * 500))
    db.commit()
    inputs = MatchingInputsService(db)
    for group in inputs.read_job(job.id)["groups"]:
        inputs.delete_group(users[1], job.id, group["id"], inputs.read_job(job.id)["fingerprint"])
    if grouped:
        for item in db.scalars(select(JobSkill).where(JobSkill.job_id == job.id)):
            inputs.create_group(users[1], job.id, group_payload(inputs.read_job(job.id), item))
        inputs.signoff(users[1], job.id, sign_payload(inputs.read_job(job.id)))
    repo = RetrievalRepository(db, TEMPLATE_V2)
    repo.upsert(profiles[0].id, "profile", repo.profile_input(profiles[0].id), [1.] + [0.] * 383)
    repo.upsert(job.id, "job", repo.job_input(job), [1.] + [0.] * 383); db.commit()
    return users, profiles, job


def verify_bounds(db):
    size = lambda value: len(json.dumps(value, ensure_ascii=False, default=str).encode())
    for row in db.scalars(select(JobMatchResult)):
        assert size(row.reason_parameters) <= 8192
    for row in db.scalars(select(SkillGapResult)):
        assert size(row.evidence_snapshot) <= 16384 and size(row.reason_parameters) <= 8192
        assert all("evidence_sentence" not in x for x in row.evidence_snapshot["candidate_confirmed_evidence"])
    for row in db.scalars(select(SkillGapAtomicResult)):
        assert size(row.reason_parameters) <= 8192


@pytest.mark.parametrize("grouped", [False, True])
def test_large_inputs_persist_without_losing_decisions_or_repeating_prose(db_session, monkeypatch, grouped):
    users, _, _ = large_inputs(db_session, grouped=grouped); sqlite_retrieval(monkeypatch)
    response = MatchingRunsService(db_session).create(users[0]); verify_bounds(db_session)
    result, = response["results"]
    if not grouped:
        assert result["alignment_fraction"] is None
        summary = result["reason_parameters"]["unknown_occurrence_summary"]
        assert summary["total"] == 20 and summary["omitted_count"] == 12
        assert len([x for x in result["gaps"] if x["status"] == "unassessed"
                    and x["reason_parameters"]["component"] is None]) == 20
    else:
        # Full 60-by-21 arithmetic is retained; only evidence prose is bounded.
        atoms = list(db_session.scalars(select(SkillGapAtomicResult)))
        assert len(atoms) == 60 * 21
        excerpts = [x.reason_parameters["candidate_evidence"] for x in atoms if "candidate_evidence" in x.reason_parameters]
        assert len(excerpts) == 60
        assert result["alignment_fraction"] == "100/21"
        assert all(x["full_source_required_for_text_reconstruction"] for x in excerpts)
        assert len({x["id"] for x in excerpts}) == 60


@pytest.mark.parametrize("sentence", ["Explicit supported practice. " * 400, "\U00010437" * 8000])
def test_excerpt_records_exact_hash_and_preserves_source_reference(sentence):
    row = {"id": str(uuid4()), "normalized_text": "Python", "evidence_reference": "source line 17",
           "evidence_sentence": sentence}
    before = deepcopy(row)
    excerpt = MatchingRunsService.evidence_excerpt(row, {"concepts": [], "links": []})
    omission = excerpt["text_omissions"]["evidence_sentence"]
    assert omission["original_sha256"] == hashlib.sha256(row["evidence_sentence"].encode()).hexdigest()
    assert excerpt["evidence_sentence"] == row["evidence_sentence"][:omission["retained_characters"]]
    assert excerpt["evidence_reference"] == row["evidence_reference"]
    assert excerpt["source_snapshot_sha256"] == fingerprint(row) and row == before


def test_near_ties_use_exact_alignment_then_rank_then_uuid_never_similarity():
    def view(n, score, rank, similarity):
        return {"job_id": UUID(int=n), "alignment_fraction": score, "original_retrieval_rank": rank,
                "retrieval_similarity": similarity}
    rows = [view(4, "50/1", 3, 1), view(3, "50/1", 3, 0), view(2, "50/1", 1, 1),
            view(5, "500000001/10000000", 2, -1), view(1, None, 1, 1)]
    assert decimal_value(Fraction(rows[0]["alignment_fraction"])) == decimal_value(Fraction(rows[3]["alignment_fraction"]))
    assert [x["job_id"].int for x in sorted(rows, key=result_order_key)] == [5, 2, 3, 4, 1]


def test_excerpt_does_not_shorten_text_that_fits():
    sentence = "A complete supported evidence sentence. " * 15
    row = {"id": str(uuid4()), "normalized_text": "Python", "evidence_sentence": sentence}
    excerpt = MatchingRunsService.evidence_excerpt(row, {"concepts": [], "links": []})
    assert excerpt["evidence_sentence"] == sentence
    assert excerpt["text_omissions"] == {} and not excerpt["full_source_required_for_text_reconstruction"]


@pytest.mark.parametrize("kind,expected", [("snapshot", 413), ("constraint", 422), ("programming", None)])
def test_persistence_failures_are_not_misreported_as_concurrency(db_session, monkeypatch, kind, expected):
    users, _, _, _ = seed_runs(db_session); sqlite_retrieval(monkeypatch)
    before = table_snapshot(db_session)
    exception = {"snapshot": SnapshotLimitError("test_snapshot"),
                 "constraint": IntegrityError("test", {}, Exception("constraint")),
                 "programming": ProgrammingError("test", {}, Exception("programming"))}[kind]
    def fail(repo): raise exception
    monkeypatch.setattr(MatchingRunsRepository, "finish", fail)
    if expected is None:
        with pytest.raises(ProgrammingError): MatchingRunsService(db_session).create(users[0])
    else:
        with pytest.raises(HTTPException) as error: MatchingRunsService(db_session).create(users[0])
        assert error.value.status_code == expected
        assert error.value.detail["code"] != "matching_concurrency_conflict"
    assert table_snapshot(db_session) == before
