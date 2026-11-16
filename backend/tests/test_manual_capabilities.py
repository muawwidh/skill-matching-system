"""Synthetic manual inventory entry; no private corpus or running application."""
from fractions import Fraction
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.auth import get_current_user
from app.db.models import JobSkill
from app.db.models.explainable import JobManualCapability, JobInventoryReview
from app.db.session import get_db
from app.main import create_app
from app.matching.assessment import assess_inputs, InputConsistencyError
from app.matching.manual_capabilities import INPUT_ADAPTER_VERSION, cleaned_hash
from app.matching.policy import normalize
from app.repositories.matching_inputs_repository import snapshot
from app.schemas.matching_inputs import CapabilityInput, GroupInput
from app.services.matching_inputs_service import MatchingInputsService
from test_matching_inputs import seed, sign_payload, group_payload


def setup(db):
    users, profiles, job, skill = seed(db)
    job.cleaned_description = "Requires Python and 🧪 Café. Preferred Git."
    db.commit()
    return users, profiles, job, skill, MatchingInputsService(db)


def payload(service, job, text="Café", **changes):
    state = service.read_job(job.id)
    start = state["cleaned_description"].index(text)
    values = dict(expected_fingerprint=state["fingerprint"], raw_text=text, skill_type="skill",
        classification="required", review_status="approved", cleaned_description_sha256=state["cleaned_description_sha256"],
        capability_start=start, capability_end=start+len(text), evidence_start=0,
        evidence_end=len(state["cleaned_description"]), evidence_sentence=state["cleaned_description"],
        review_reason="Human source-bound transcription", ledger_reference="synthetic decision 1", no_local_file_anchor=True)
    values.update(changes)
    return CapabilityInput(**values)


def manual_group(service, job, manual, **changes):
    values = dict(expected_fingerprint=service.read_job(job.id)["fingerprint"], component="R", operator="SINGLE",
        classification="required", critical=False, review_status="approved", members=[{"manual_capability_id": manual["id"]}])
    values.update(changes)
    return GroupInput(**values)


def test_unicode_source_inventory_only_and_human_attribution(db_session):
    users, _, job, _, service = setup(db_session)
    before = service.read_job(job.id)
    job_before = snapshot(job)
    created = service.create_capability(users[2], job.id, payload(service, job))
    assert created["capability_start"] == job.cleaned_description.index("Café")
    assert created["reviewed_by"] == users[2].id
    assert created["reviewer_pseudonym_snapshot"].startswith("reviewer_")
    assert created["provenance"] == "manual_transcription"
    after = service.read_job(job.id)
    assert after["source_fingerprint"] == before["source_fingerprint"]
    assert after["fingerprint"] != before["fingerprint"]
    assert after["cleaned_description_sha256"] == cleaned_hash(job.cleaned_description)
    assert after["input_adapter_version"] == INPUT_ADAPTER_VERSION
    assert snapshot(job) == job_before
    assert not db_session.new and not db_session.dirty


@pytest.mark.parametrize("status", ["pending", "rejected", "approved"])
def test_all_extraction_review_states_block_manual_creation(db_session, status):
    users, _, job, skill, service = setup(db_session)
    skill.review_status = status
    skill.normalized_text = "  CAFÉ  "
    db_session.commit()
    with pytest.raises(HTTPException, match="unrepresented"):
        service.create_capability(users[1], job.id, payload(service, job, skill_type="tool"))
    assert not list(db_session.scalars(select(JobManualCapability)))


def test_duplicate_family_normalization_and_overlap_warning(db_session):
    users, _, job, _, service = setup(db_session)
    service.create_capability(users[1], job.id, payload(service, job))
    with pytest.raises(HTTPException):
        service.create_capability(users[1], job.id, payload(service, job, skill_type="tool"))
    other = service.create_capability(users[1], job.id, payload(service, job, "Git"))
    assert other["warnings"] == ["evidence_span_overlap"]
    assert normalize("Café") == normalize("  CAFÉ ")


@pytest.mark.parametrize("changes", [dict(raw_text="Wrong"), dict(cleaned_description_sha256="0"*64),
    dict(capability_start=24, capability_end=28), dict(evidence_end=999)])
def test_source_hash_and_codepoint_mismatch_rejected(db_session, changes):
    users, _, job, _, service = setup(db_session)
    with pytest.raises(HTTPException):
        service.create_capability(users[1], job.id, payload(service, job, **changes))


def test_schema_no_spoofing_lengths_review_states_or_partial_anchors(db_session):
    _, _, job, _, service = setup(db_session)
    original = payload(service, job).model_dump()
    for changes in ({"review_status": "pending"}, {"reviewed_by": str(uuid4())},
                    {"normalized_text": "invented"}, {"classification": "unknown"},
                    {"raw_text": "x"*256}, {"local_start": 0}, {"no_local_file_anchor": False}):
        with pytest.raises(ValueError): CapabilityInput(**(original | changes))


@pytest.mark.parametrize("status", ["pending", "rejected", "approved"])
def test_signoff_assessment_later_conflicts_and_missing_groups(db_session, status):
    users, profiles, job, skill, service = setup(db_session)
    created = service.create_capability(users[1], job.id, payload(service, job))
    service.create_group(users[1], job.id, group_payload(service.read_job(job.id), skill))
    with pytest.raises(HTTPException): service.signoff(users[1], job.id, sign_payload(service.read_job(job.id)))
    group = service.create_group(users[1], job.id, manual_group(service, job, created))
    service.signoff(users[1], job.id, sign_payload(service.read_job(job.id)))
    assert service.read_job(job.id)["inventory_current"]
    candidate = service.read_candidate(users[0])
    # Assessment must catch later extractor changes, including rejected occurrences.
    skill.normalized_text = "café"; skill.review_status = status; db_session.commit()
    state = service.read_job(job.id)
    with pytest.raises(InputConsistencyError, match="conflict"):
        assess_inputs(candidate, state, frozenset())
    with pytest.raises(HTTPException): service.signoff(users[1], job.id, sign_payload(state))
    assert group["id"]


def test_later_source_mismatch_blocks_signoff_and_assessment(db_session):
    users, _, job, _, service = setup(db_session)
    service.create_capability(users[1], job.id, payload(service, job))
    job.cleaned_description += " Source changed"; db_session.commit()
    state = service.read_job(job.id)
    with pytest.raises(HTTPException, match="manual_source_mismatch"):
        service.signoff(users[1], job.id, sign_payload(state))
    with pytest.raises(InputConsistencyError) as exc:
        assess_inputs(service.read_candidate(users[0]), state, frozenset())
    assert exc.value.code == "manual_source_mismatch"


def test_manual_group_scoring_uses_unchanged_text_only_engine(db_session):
    from app.db.models import CandidateSkill
    users, _, job, skill, service = setup(db_session)
    db_session.delete(skill); db_session.commit()
    profile = service.profile(users[0])
    db_session.add(CandidateSkill(candidate_profile_id=profile.id, raw_text="Café", normalized_text="café",
                                  skill_type="tool", review_status="approved")); db_session.commit()
    created = service.create_capability(users[1], job.id, payload(service, job))
    service.create_group(users[1], job.id, manual_group(service, job, created))
    service.signoff(users[1], job.id, sign_payload(service.read_job(job.id)))
    result = assess_inputs(service.read_candidate(users[0]), service.read_job(job.id), frozenset())
    assert result["assessment"]["exact_fraction"] == "100/1"
    assert result["groups"][0]["support"] == Fraction(1)
    assert result["evidence"][0]["reason_code"] == "text_only_match"
    assert result["evidence"][0]["requirement_origin"] == "phase6_manual_capability"


def test_delete_group_guard_stale_expected_rollback_and_criticality(db_session, monkeypatch):
    users, _, job, _, service = setup(db_session)
    created = service.create_capability(users[1], job.id, payload(service, job))
    with pytest.raises(ValueError): manual_group(service, job, created, critical=True)
    group = service.create_group(users[1], job.id, manual_group(service, job, created,
        critical=True, critical_rationale="Source explicitly marks Café essential"))
    with pytest.raises(HTTPException): service.delete_capability(users[1], job.id, created["id"], service.read_job(job.id)["fingerprint"])
    service.delete_group(users[1], job.id, group["id"], service.read_job(job.id)["fingerprint"])
    before = service.read_job(job.id)
    with pytest.raises(HTTPException): service.delete_capability(users[1], job.id, created["id"], "0"*64)
    def fail():
        db_session.flush()
        raise RuntimeError("rollback seam")
    monkeypatch.setattr(service.repo, "finish", fail)
    with pytest.raises(RuntimeError): service.delete_capability(users[1], job.id, created["id"], before["fingerprint"])
    assert service.read_job(job.id) == before


def test_api_manager_only_readonly_and_foreign_job_404(db_session):
    users, _, job, _, service = setup(db_session)
    app = create_app(); app.dependency_overrides[get_db] = lambda: db_session
    path = f"/matching-inputs/jobs/{job.id}/capabilities"
    with TestClient(app) as client:
        body = payload(service, job).model_dump()
        assert client.post(path, json=body).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: users[0]
        assert client.post(path, json=body).status_code == 403
        for user in users[1:3]:
            app.dependency_overrides[get_current_user] = lambda: user
            assert client.get(f"/matching-inputs/jobs/{job.id}/inventory").status_code == 200
        created = client.post(path, json=body)
        assert created.status_code == 201
        assert client.delete(f"/matching-inputs/jobs/{uuid4()}/capabilities/{created.json()['id']}?expected_fingerprint={'0'*64}").status_code == 404
    assert not db_session.new and not db_session.dirty


def test_old_adapter_cannot_be_current_even_with_current_hash(db_session, monkeypatch):
    from test_matching_runs import seed_runs, sqlite_retrieval, runs_service
    from app.db.models.explainable import MatchingRun
    users, _, job, _ = seed_runs(db_session)
    sqlite_retrieval(monkeypatch)
    run_service = runs_service(db_session)
    run = run_service.create(users[0])
    assert run["current"]
    row = db_session.get(MatchingRun, run["run_id"])
    # SQLite deliberately permits simulation of historical rows; PostgreSQL
    # migration tests below prove old rows remain NULL, without rewriting tags.
    row.input_adapter_version = None; db_session.commit()
    before = snapshot(row)
    view = run_service.read(users[0], row.id)
    assert not view["current"] and "input_adapter_version_mismatch" in view["readiness"]["warnings"]
    assert snapshot(row) == before
    review = db_session.scalar(select(JobInventoryReview).where(JobInventoryReview.job_id == job.id))
    review.input_adapter_version = None; db_session.commit()
    assert not MatchingInputsService(db_session).read_job(job.id)["inventory_current"]


def test_long_manual_excerpt_remains_bounded_with_source_anchors(db_session):
    import json
    from app.services.matching_runs_service import MatchingRunsService
    users, _, job, _, service = setup(db_session)
    job.cleaned_description = "🧪" * 900; db_session.commit()
    cap = service.create_capability(users[1], job.id, payload(service, job, "🧪" * 200,
        review_reason="🧪"*1000))
    excerpt = MatchingRunsService.evidence_excerpt(cap, {"terms": [], "links": [], "concepts": []})
    assert len(json.dumps(excerpt, ensure_ascii=False).encode()) <= 3200
    assert excerpt["capability_start"] == 0 and excerpt["capability_end"] == 200
    assert excerpt["cleaned_description_sha256"] == cleaned_hash(job.cleaned_description)
    assert excerpt["text_omissions"] and excerpt["provenance"] == "manual_transcription"
