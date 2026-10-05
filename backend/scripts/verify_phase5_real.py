"""One-shot, de-identified Phase 5 evidence run; only phase5_verify is allowed."""
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.db.models import (ApprovedTaxonomyLink, CandidateJobMatch, CandidateProfile,
    CandidateProfileEmbedding, CandidateSkill, CvDocument, ExtractedCandidateTerm,
    ExtractedJobTerm, Job, JobEmbedding, JobSkill, Role, TaxonomyConcept,
    TaxonomyLinkCandidate, TaxonomySource, TaxonomyVersion, User)
from app.db.models.taxonomy import TaxonomyReviewEvent
from app.db.session import get_db
from app.main import create_app
from app.repositories.document_repository import DocumentRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.embedder import LocalE5Embedder
from app.retrieval.representation import DIMENSION, MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION
from app.services.retrieval_service import RetrievalService


def timed(call):
    start = perf_counter()
    result = call()
    return result, round((perf_counter() - start) * 1000, 3)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_files(path: Path) -> tuple[list[dict], int]:
    files = []
    for item in sorted(path.rglob("*")):
        if item.is_file() and ".cache" not in item.parts:
            files.append({"filename": str(item.relative_to(path)), "bytes": item.stat().st_size,
                          "sha256": sha256_file(item)})
    return files, sum(item["bytes"] for item in files)


def seed_0007(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    candidate = User(email="phase5-verify@example.invalid", full_name="Deidentified Candidate", hashed_password="unused")
    candidate.roles.append(Role(name="candidate", description=""))
    admin = User(email="phase5-admin@example.invalid", full_name="Deidentified Admin", hashed_password="unused")
    admin.roles.append(Role(name="admin", description=""))
    source = TaxonomySource(code="ESCO", name="Verification fixture", homepage_url="", description="")
    db.add_all([candidate, admin, source])
    db.flush()
    release = TaxonomyVersion(source_id=source.id, version="verification-1.2.1", imported_at=now,
                              status="active", is_sample=True, import_filename="fixture", checksum="0" * 64)
    db.add(release)
    db.flush()
    concepts = {}
    for word, label in (("Python", "Python programming"), ("Rust", "Rust programming"),
                        ("Go", "Go programming")):
        concept = TaxonomyConcept(taxonomy_version_id=release.id, external_id=f"verify:{word}",
            preferred_label=label, normalized_label=label.lower(), concept_type="skill", language="en")
        db.add(concept)
        db.flush()
        concepts[word] = concept
    profile = CandidateProfile(user_id=candidate.id, consent_to_process_cv=True)
    db.add(profile)
    db.flush()
    cv = CvDocument(candidate_profile_id=profile.id, content_type="text/plain", source="verification",
                    status="processed", original_filename="deidentified.txt", raw_text="", cleaned_text="")
    db.add(cv)
    db.flush()
    candidate_terms = {}
    for word, status in (("Python", "approved"), ("Rust", "pending"), ("Go", "rejected")):
        term = ExtractedCandidateTerm(cv_document_id=cv.id, raw_text=word, normalized_text=word.lower(),
            term_type="skill", evidence_sentence=f"De-identified {word} evidence", extraction_method="fixture",
            review_status=status)
        db.add(term)
        db.flush()
        db.add(CandidateSkill(candidate_profile_id=profile.id, extracted_term_id=term.id,
            raw_text=word, normalized_text=word.lower(), skill_type="skill",
            evidence_sentence=f"De-identified {word} evidence", review_status=status, source="extraction"))
        proposal = TaxonomyLinkCandidate(term_source="candidate", extracted_term_id=term.id,
            raw_text=word, normalized_text=word.lower(), concept_id=concepts[word].id,
            match_method="exact_preferred", confidence_score=1.0, rank=1,
            review_status="approved", reviewed_by=admin.id, reviewed_at=now)
        db.add(proposal)
        db.flush()
        db.add(ApprovedTaxonomyLink(term_source="candidate", extracted_term_id=term.id,
            concept_id=concepts[word].id, link_candidate_id=proposal.id,
            match_method="exact_preferred", confidence_score=1.0,
            approval_source="fixture", approved_by=admin.id, approved_at=now))
        candidate_terms[word] = term
    first = next(iter(candidate_terms.values()))
    db.add(TaxonomyReviewEvent(term_source="candidate", extracted_term_id=first.id,
        candidate_id=uuid4(), action="approved", reviewer_id=admin.id,
        created_at=now, before_state={"selection": None}, after_state={"selection": "fixture"}))
    jobs = {}
    specs = [
        ("tie_low", UUID(int=101), "Python API Engineer", "Vilnius", "Build analytics APIs", "Python", "SQL", "processed"),
        ("tie_high", UUID(int=102), "Python API Engineer", "Vilnius", "Build analytics APIs", "Python", "SQL", "processed"),
        ("different", UUID(int=103), "Support Analyst", "Kaunas", "Support customers", "Communication", "Excel", "processed"),
        ("stale", UUID(int=104), "Backend Developer", "Vilnius", "Build services", "FastAPI", "SQL", "processed"),
        ("archived", UUID(int=105), "Archived Engineer", "Vilnius", "Build analytics APIs", "Python", "SQL", "archived"),
    ]
    for key, job_id, title, location, description, required, preferred, status in specs:
        job = Job(id=job_id, title=title, company="Deidentified", location=location,
            employment_type="full time", description=description,
            cleaned_description=description, status=status)
        db.add(job)
        db.flush()
        for word, requirement in ((required, "required"), (preferred, "preferred")):
            term = ExtractedJobTerm(job_id=job.id, raw_text=word, normalized_text=word.lower(),
                term_type="skill", extraction_method="fixture", requirement_type=requirement,
                review_status="pending")
            db.add(term)
            db.flush()
            db.add(JobSkill(job_id=job.id, extracted_term_id=term.id, raw_text=word,
                normalized_text=word.lower(), skill_type="skill", requirement_type=requirement,
                review_status="pending", source="extraction"))
            if word == "Python":
                db.add(ApprovedTaxonomyLink(term_source="job", extracted_term_id=term.id,
                    concept_id=concepts[word].id, match_method="exact_preferred",
                    confidence_score=1.0, approval_source="fixture", approved_by=admin.id, approved_at=now))
        jobs[key] = job.id
    db.add(CandidateJobMatch(candidate_profile_id=profile.id, job_id=jobs["tie_low"],
        score=77.0, matched_required=[], matched_preferred=[], missing_required=[],
        missing_preferred=[], candidate_skill_count=1, job_skill_count=2,
        explanation="Preexisting Phase 4 prototype score"))
    db.commit()
    return {"candidate_id": candidate.id, "admin_id": admin.id, "profile_id": profile.id,
            "approved_skill_id": db.scalar(select(CandidateSkill.id).where(
                CandidateSkill.candidate_profile_id == profile.id,
                CandidateSkill.review_status == "approved")), "jobs": jobs}


def review_snapshot(db: Session) -> dict:
    return {
        "links": sorted((str(row.extracted_term_id), str(row.concept_id), row.approval_source)
                        for row in db.scalars(select(ApprovedTaxonomyLink))),
        "candidates": sorted((str(row.id), row.review_status, str(row.concept_id))
                             for row in db.scalars(select(TaxonomyLinkCandidate))),
        "events": sorted((str(row.id), row.action) for row in db.scalars(select(TaxonomyReviewEvent))),
        "score": db.scalar(select(CandidateJobMatch.score)),
    }


def run_cli(scoped_url: str, kind: str, limit: int = 10) -> tuple[dict, float]:
    environment = dict(os.environ, DATABASE_URL=scoped_url, HF_HUB_OFFLINE="1",
                       TRANSFORMERS_OFFLINE="1")
    command_line = [sys.executable, "-m", "app.retrieval.cli", "index", kind, "--limit", str(limit)]
    completed, duration = timed(lambda: subprocess.run(command_line, env=environment,
        capture_output=True, text=True, check=True))
    return json.loads(completed.stdout.splitlines()[-1]), duration


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    if make_url(database_url).database != "phase5_verify":
        raise RuntimeError("Refusing any database except isolated phase5_verify.")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise RuntimeError("Offline model modes must be enabled.")
    model_path = Path(os.environ["DENSE_MODEL_PATH"])
    files, total_bytes = model_files(model_path)
    revision = (model_path / "revision.txt").read_text().strip()
    metadata_revision = (model_path / ".cache/huggingface/download/model.safetensors.metadata").read_text().splitlines()[0]
    assert revision == metadata_revision == MODEL_REVISION
    versions = {name: importlib.metadata.version(name) for name in
        ("sentence-transformers", "transformers", "torch", "pgvector", "numpy", "huggingface-hub")}
    model, load_ms = timed(lambda: LocalE5Embedder(str(model_path)))
    vector, cold_encode_ms = timed(lambda: model.encode("query: Python programming"))
    _, warm_encode_ms = timed(lambda: model.encode("query: Python programming"))
    job_text = "passage: Job title: Python API Engineer\nRequired skills: Python; Python programming\nPreferred skills: SQL"
    _, job_first_encode_ms = timed(lambda: model.encode(job_text))
    _, job_warm_encode_ms = timed(lambda: model.encode(job_text))
    assert len(vector) == DIMENSION
    with tempfile.TemporaryDirectory() as temporary:
        bad = Path(temporary)
        (bad / "modules.json").write_text("{}")
        (bad / "revision.txt").write_text("incorrect")
        try:
            LocalE5Embedder(str(bad))
        except RuntimeError as exc:
            assert "pinned revision" in str(exc)
        else:
            raise AssertionError("Incorrect model revision was accepted")
    del model
    gc.collect()

    admin_engine = create_engine(database_url)
    schema = "phase5_real_" + uuid4().hex
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped_url = make_url(database_url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    engine = create_engine(scoped_url)
    settings.DATABASE_URL = scoped_url
    config = Config("alembic.ini")
    evidence = {}
    try:
        command.upgrade(config, "0007_taxonomy_review_audit")
        with Session(engine) as db:
            ids = seed_0007(db)
            baseline = review_snapshot(db)
        command.upgrade(config, "0008_dense_retrieval")
        with engine.connect() as connection:
            assert connection.scalar(text("select version_num from alembic_version")) == "0008_dense_retrieval"
            vector_extension = connection.scalar(text("select extversion from pg_extension where extname='vector'"))
        with Session(engine) as db:
            candidate_text = RetrievalRepository(db).profile_input(ids["profile_id"]).text
            assert "Python programming" in candidate_text
            assert "Rust" not in candidate_text and "Go" not in candidate_text
            assert "De-identified Python evidence" in candidate_text
            assert "De-identified Rust evidence" not in candidate_text
            job_text = RetrievalRepository(db).job_input(db.get(Job, ids["jobs"]["tie_low"])).text
            assert "Required skills: Python; Python programming" in job_text
            assert "Preferred skills: SQL" in job_text
        jobs_initial, jobs_initial_ms = run_cli(scoped_url, "jobs")
        profiles_initial, profiles_initial_ms = run_cli(scoped_url, "profiles")
        jobs_again, _ = run_cli(scoped_url, "jobs")
        profiles_again, _ = run_cli(scoped_url, "profiles")
        assert jobs_initial["counts"] == {"indexed": 4, "unchanged": 0, "not_ready": 1, "failed": 0}
        assert profiles_initial["counts"]["indexed"] == 1
        assert jobs_again["counts"]["unchanged"] == 4
        assert profiles_again["counts"]["unchanged"] == 1

        with Session(engine) as db:
            user = db.get(User, ids["candidate_id"])
            service = RetrievalService(db)
            results = service.jobs_for_user(user, 20)
            tie_ids = [row["job_id"] for row in results if row["job_id"] in
                       {ids["jobs"]["tie_low"], ids["jobs"]["tie_high"]}]
            assert tie_ids == sorted(tie_ids) and len(tie_ids) == 2
            assert ids["jobs"]["archived"] not in [row["job_id"] for row in results]
            assert len(results) == 4
            extra = JobEmbedding(job_id=ids["jobs"]["tie_low"], embedding=[0.0, 1.0] + [0.0] * 382,
                model_id=MODEL_ID, model_revision="wrong", template_version=TEMPLATE_VERSION,
                source_hash="x" * 64, taxonomy_fingerprint="x" * 64, status="ready")
            db.add(extra)
            db.commit()
        with Session(engine) as db:
            assert len(RetrievalService(db).jobs_for_user(db.get(User, ids["candidate_id"]), 20)) == 4
            skill = db.get(CandidateSkill, ids["approved_skill_id"])
            DocumentRepository(db).update_candidate_skill(skill, skill.raw_text, skill.normalized_text,
                skill.skill_type, "Updated de-identified Python evidence", "approved")
            job_skill = db.scalar(select(JobSkill).where(JobSkill.job_id == ids["jobs"]["stale"]).limit(1))
            DocumentRepository(db).update_job_skill(job_skill, job_skill.raw_text, job_skill.normalized_text,
                job_skill.skill_type, job_skill.requirement_type, "Updated job evidence", job_skill.review_status)
            db.commit()
            assert db.scalar(select(CandidateProfileEmbedding.status)) == "stale"
            assert db.scalar(select(JobEmbedding.status).where(JobEmbedding.job_id == ids["jobs"]["stale"])) == "stale"
            class Failure:
                def encode(self, _):
                    raise RuntimeError("injected inference failure")
            try:
                RetrievalService(db).index_job(ids["jobs"]["stale"], Failure())
            except RuntimeError:
                db.rollback()
            else:
                raise AssertionError("Injected failure was not raised")
        with Session(engine) as db:
            assert db.scalar(select(JobEmbedding.status).where(JobEmbedding.job_id == ids["jobs"]["stale"])) == "stale"
            try:
                RetrievalService(db).jobs_for_user(db.get(User, ids["candidate_id"]), 20)
            except Exception as exc:
                assert getattr(exc, "status_code", None) == 409
            else:
                raise AssertionError("Stale candidate vector was returned")
        jobs_refresh, _ = run_cli(scoped_url, "jobs")
        profiles_refresh, _ = run_cli(scoped_url, "profiles")
        assert jobs_refresh["counts"]["indexed"] == 1
        assert profiles_refresh["counts"]["indexed"] == 1

        with Session(engine) as db:
            db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == ids["jobs"]["stale"],
                JobEmbedding.model_revision == MODEL_REVISION)).status = "stale"
            db.commit()
        with Session(engine) as db:
            user = db.get(User, ids["candidate_id"])
            service = RetrievalService(db)
            filtered = service.jobs_for_user(user, 20)
            assert ids["jobs"]["stale"] not in [row["job_id"] for row in filtered]
            assert len(filtered) == 3
        jobs_final, _ = run_cli(scoped_url, "jobs")
        assert jobs_final["counts"]["indexed"] == 1

        def session_override():
            with Session(engine) as db:
                yield db
        app = create_app()
        app.dependency_overrides[get_db] = session_override
        with Session(engine) as db:
            app.dependency_overrides[get_current_user] = lambda: db.get(User, ids["candidate_id"])
            with TestClient(app) as client:
                response, api_ms = timed(lambda: client.get("/retrieval/jobs?limit=20"))
                assert response.status_code == 200, response.text
                assert len(response.json()) == 4
                assert all("retrieval_similarity" in row for row in response.json())
            app.dependency_overrides[get_current_user] = lambda: db.get(User, ids["admin_id"])
            with TestClient(app) as client:
                assert client.get("/retrieval/jobs").status_code == 403

        query_ms = []
        service_ms = []
        with Session(engine) as db:
            repo = RetrievalRepository(db)
            service = RetrievalService(db)
            query = repo.profile_embedding(ids["profile_id"])
            user = db.get(User, ids["candidate_id"])
            for _ in range(5):
                _, latency = timed(lambda: repo.exact_jobs(query, 20))
                query_ms.append(latency)
                _, latency = timed(lambda: service.jobs_for_user(user, 20))
                service_ms.append(latency)
            assert review_snapshot(db) == baseline
            assert db.scalar(select(CandidateJobMatch.score)) == 77.0

        evidence = {
            "scope": "de-identified representative fixture; no human relevance labels",
            "database": "phase5_verify", "schema_removed_after_verification": True,
            "migration_from": "0007_taxonomy_review_audit", "verified_migration": "0008_dense_retrieval",
            "vector_extension_version": vector_extension,
            "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "resolved_metadata_revision": metadata_revision,
                      "dimension": DIMENSION, "template_version": TEMPLATE_VERSION,
                      "artifact_bytes": total_bytes, "files": files},
            "runtime": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "architecture": platform.machine(), "cpu_count_visible": os.cpu_count(),
                        "packages": versions, "offline_modes": ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"],
                        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
            "fixture_counts": {"candidate_profiles": 1, "approved_candidate_occurrences": 1,
                               "pending_candidate_occurrences": 1, "rejected_candidate_occurrences": 1,
                               "active_jobs": 4, "archived_jobs": 1},
            "checks": {"offline_loading": True, "wrong_revision_rejected": True,
                       "approved_only_candidate_representation": True, "canonical_label_included": True,
                       "required_preferred_distinct": True, "cli_idempotent": True,
                       "stale_invalidation_and_refresh": True, "injected_failure_retry": True,
                       "archived_stale_wrong_revision_excluded": True, "deterministic_tie_order": True,
                       "fresh_session_api_and_permissions": True, "phase4_review_unchanged": True,
                       "candidate_job_match_score_unchanged": True},
            "performance": {"model_load_ms": load_ms, "cold_single_encode_ms": cold_encode_ms,
                            "warm_single_encode_ms": warm_encode_ms,
                            "job_first_encode_ms": job_first_encode_ms,
                            "job_warm_encode_ms": job_warm_encode_ms,
                            "cli_initial_job_batch": jobs_initial, "cli_initial_profile_batch": profiles_initial,
                            "job_batch_indexed_per_second_excluding_load": round(
                                jobs_initial["counts"]["indexed"] / jobs_initial["duration_seconds"], 3),
                            "cli_job_wall_ms_including_startup": jobs_initial_ms,
                            "cli_profile_wall_ms_including_startup": profiles_initial_ms,
                            "postgres_exact_query_ms": query_ms,
                            "postgres_exact_query_mean_ms": round(mean(query_ms), 3),
                            "service_query_ms": service_ms,
                            "service_query_mean_ms": round(mean(service_ms), 3),
                            "api_request_ms": api_ms},
            "human_labelled_retrieval_quality": "PENDING",
        }
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
    output = Path(os.environ["PHASE5_EVIDENCE_PATH"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"evidence": str(output), "checks": evidence["checks"],
                      "performance": evidence["performance"]}))


if __name__ == "__main__":
    main()
