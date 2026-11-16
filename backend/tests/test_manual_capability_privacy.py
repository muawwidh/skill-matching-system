"""Candidate-facing evidence isolation, including immutable legacy snapshots."""
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.auth import get_current_user
from app.db.models.explainable import JobMatchResult, MatchScoreComponent, SkillGapResult, SkillGapAtomicResult, MatchingRun
from app.db.session import get_db
from app.main import create_app
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import TEMPLATE_V2, DIMENSION
from app.services.matching_inputs_service import MatchingInputsService
from app.services.matching_runs_service import MatchingRunsService
from test_manual_capabilities import payload, manual_group
from test_matching_inputs import group_payload, sign_payload
from test_matching_runs import seed_runs, sqlite_retrieval, table_snapshot

PRIVATE = {
    "ledger_reference": "PRIVATE_LEDGER_b1",
    "review_reason": "PRIVATE_REVIEW_REASON_b1",
    "local_source_sha256": "d"*64,
    "local_line_start": 91001, "local_line_end": 91002,
    "local_start": 92001, "local_end": 92002,
    "no_local_file_anchor": False,
    "critical_source_rationale": "PRIVATE_CRITICAL_RATIONALE_b1",
    "manager_only_annotation": "PRIVATE_MANAGER_ANNOTATION_b1",
}


def assert_private_absent(value):
    if isinstance(value, dict):
        assert not (set(value) & set(PRIVATE))
        assert not any(key.startswith("local_") for key in value)
        for child in value.values(): assert_private_absent(child)
    elif isinstance(value, (list, tuple)):
        for child in value: assert_private_absent(child)
    serialized = json.dumps(value, default=str)
    for marker in PRIVATE.values():
        if not isinstance(marker, bool): assert str(marker) not in serialized


def prepare(db):
    users, _, job, skill = seed_runs(db)
    job.cleaned_description = "Requires Python and Git."; db.commit()
    inputs = MatchingInputsService(db)
    old = inputs.read_job(job.id)["groups"][0]
    inputs.delete_group(users[1], job.id, old["id"], inputs.read_job(job.id)["fingerprint"])
    inputs.create_group(users[1], job.id, group_payload(inputs.read_job(job.id), skill))
    values = {key: value for key, value in PRIVATE.items() if key not in {"critical_source_rationale", "manager_only_annotation"}}
    cap = inputs.create_capability(users[1], job.id, payload(inputs, job, "Git", **values))
    inputs.create_group(users[1], job.id, manual_group(inputs, job, cap, critical=True,
        critical_rationale=PRIVATE["critical_source_rationale"]))
    inputs.signoff(users[1], job.id, sign_payload(inputs.read_job(job.id)))
    retrieval = RetrievalRepository(db, TEMPLATE_V2)
    retrieval.upsert(job.id, "job", retrieval.job_input(job), [1.0]+[0.0]*(DIMENSION-1)); db.commit()
    return users, job, cap


def check_new_and_historical(db, users, job, cap):
    service = MatchingRunsService(db)
    response = service.create(users[0])
    assert_private_absent(response)
    rid = response["run_id"]
    atoms = list(db.scalars(select(SkillGapAtomicResult)))
    manual = next(a.reason_parameters["requirement_evidence"] for a in atoms
                  if a.reason_parameters.get("requirement_origin") == "phase6_manual_capability")
    assert manual["id"] == str(cap["id"])
    assert manual["cleaned_description_sha256"] == cap["cleaned_description_sha256"]
    assert manual["capability_start"] == cap["capability_start"]
    assert manual["provenance"] == "manual_transcription"
    assert manual["reviewer_pseudonym_snapshot"] == cap["reviewer_pseudonym_snapshot"]
    for row in atoms: assert_private_absent(row.reason_parameters)
    for row in db.scalars(select(SkillGapResult)): assert_private_absent(row.evidence_snapshot)
    # Simulate historical snapshots from the vulnerable implementation. Only
    # synthetic fixtures are changed; production history is never rewritten.
    run = db.get(MatchingRun, rid)
    run.provenance_snapshot = {**run.provenance_snapshot, **PRIVATE}
    for row in db.scalars(select(JobMatchResult)):
        row.reason_parameters = {**row.reason_parameters, **PRIVATE,
            "inventory_review": {**row.reason_parameters["inventory_review"], **PRIVATE}}
    for row in db.scalars(select(MatchScoreComponent)):
        row.reason_parameters = {**row.reason_parameters, **PRIVATE,
            "coverage_fraction": {"review_reason": PRIVATE["review_reason"]}}
    for row in db.scalars(select(SkillGapResult)):
        row.reason_parameters = {**row.reason_parameters, **PRIVATE}
        row.evidence_snapshot = {**row.evidence_snapshot, **PRIVATE,
            "group_review": {**row.evidence_snapshot["group_review"], **PRIVATE}}
    for row in atoms:
        extra = {"requirement_evidence": {**row.reason_parameters["requirement_evidence"], **PRIVATE,
            "text_omissions": {"review_reason": {"original_sha256": PRIVATE["local_source_sha256"]}},
            "comparison_fingerprints": {"local_source_sha256": PRIVATE["local_source_sha256"]}}}
        row.reason_parameters = {**row.reason_parameters, **PRIVATE, **extra}
    db.commit()
    before = table_snapshot(db)
    app = create_app(); app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[0]
    with TestClient(app) as client:
        for endpoint in (f"/matching-runs/{rid}", "/matching-runs/current"):
            result = client.get(endpoint)
            assert result.status_code == 200
            assert_private_absent(result.json())
        assert client.get(f"/matching-inputs/jobs/{job.id}/inventory").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: users[1]
        inventory = client.get(f"/matching-inputs/jobs/{job.id}/inventory")
        assert inventory.status_code == 200
        retained = next(x for x in inventory.json()["manual_capabilities"] if x["id"] == str(cap["id"]))
        for key, value in PRIVATE.items():
            if key not in {"critical_source_rationale", "manager_only_annotation"}: assert retained[key] == value
        assert any(g["evidence_snapshot"].get("critical_source_rationale") == PRIVATE["critical_source_rationale"]
                   for g in inventory.json()["groups"])
    assert table_snapshot(db) == before
    return rid, users[0].id


def test_candidate_api_isolates_new_and_historical_manual_metadata(db_session, monkeypatch):
    users, job, cap = prepare(db_session)
    sqlite_retrieval(monkeypatch)
    check_new_and_historical(db_session, users, job, cap)
