import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (CandidateJobMatch, CandidateProfile, CandidateProfileEmbedding, CandidateSkill,
                           Job, JobEmbedding, JobSkill, User)
from app.services.retrieval_service import RetrievalService
from test_retrieval import FakeEmbedder
from test_taxonomy_postgres import seed_0005


@pytest.fixture
def pg_retrieval(monkeypatch):
    url_text = os.environ.get("PHASE5_TEST_DATABASE_URL") or os.environ.get("PHASE4_TEST_DATABASE_URL")
    if not url_text:
        pytest.skip("UNVERIFIED: isolated PostgreSQL test URL is not set")
    url = make_url(url_text)
    if url.database not in {"phase4_verify", "phase5_verify"}:
        pytest.fail("Only an isolated verification database may be used")
    schema = "phase5_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "DATABASE_URL", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "0005_taxonomy_integration")
        with engine.begin() as connection:
            seed_0005(connection)
        command.upgrade(config, "0007_taxonomy_review_audit")
        with Session(engine) as db:
            user = db.scalars(select(User).order_by(User.email)).first()
            profile = CandidateProfile(user_id=user.id, consent_to_process_cv=True)
            job = Job(title="Python Engineer", company="Example", location="Vilnius",
                      employment_type="full time", description="Build Python APIs",
                      cleaned_description="Build Python APIs", status="processed")
            db.add_all([profile, job])
            db.flush()
            db.add_all([CandidateSkill(candidate_profile_id=profile.id, raw_text="Python",
                            normalized_text="python", review_status="approved", source="manual_review"),
                        JobSkill(job_id=job.id, raw_text="Python", normalized_text="python",
                            requirement_type="required", review_status="pending", source="manual_review"),
                        CandidateJobMatch(candidate_profile_id=profile.id, job_id=job.id, score=77,
                            matched_required=[], matched_preferred=[], missing_required=[], missing_preferred=[],
                            candidate_skill_count=1, job_skill_count=1, explanation="Preexisting score")])
            db.commit()
            profile_id, job_id, user_id = profile.id, job.id, user.id
        command.upgrade(config, "0008_dense_retrieval")
        yield engine, config, profile_id, job_id, user_id
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_populated_upgrade_extension_dimension_downgrade_reupgrade(pg_retrieval):
    engine, config, profile_id, job_id, user_id = pg_retrieval
    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == "0008_dense_retrieval"
        assert connection.scalar(text("select extversion from pg_extension where extname='vector'"))
        assert connection.scalar(text("select format_type(a.atttypid,a.atttypmod) from pg_attribute a "
            "where a.attrelid='job_embeddings'::regclass and a.attname='embedding'")) == "vector(384)"
        assert connection.scalar(text("select count(*) from taxonomy_concepts")) == 3
        assert connection.scalar(text("select count(*) from approved_taxonomy_links")) == 2
        assert connection.scalar(text("select score from candidate_job_matches")) == 77
    command.downgrade(config, "0007_taxonomy_review_audit")
    with engine.connect() as connection:
        assert connection.scalar(text("select count(*) from candidate_skills")) == 1
        assert connection.scalar(text("select to_regclass('job_embeddings')")) is None
    command.upgrade(config, "0008_dense_retrieval")
    with engine.connect() as connection:
        assert connection.scalar(text("select count(*) from jobs")) == 1


def test_fresh_session_cosine_tie_filters_uniqueness_cascade_and_retry(pg_retrieval):
    engine, _, profile_id, job_id, user_id = pg_retrieval
    fake = FakeEmbedder()
    with Session(engine) as db:
        service = RetrievalService(db)
        assert service.index_profile(profile_id, fake).outcome == "indexed"
        assert service.index_job(job_id, fake).outcome == "indexed"
        other = Job(title="Python Developer", company="Other", location="", description="Python",
                    cleaned_description="Python", status="processed")
        archived = Job(title="Python Archived", company="Other", location="", description="Python",
                       cleaned_description="Python", status="archived")
        db.add_all([other, archived])
        db.flush()
        assert service.index_job(other.id, fake).outcome == "indexed"
        assert service.index_job(archived.id, fake).outcome == "not_ready"
        other_id = other.id
        archived_id = archived.id
        db.commit()
    with Session(engine) as fresh:
        user = fresh.get(User, user_id)
        matches = RetrievalService(fresh).jobs_for_user(user, 20)
        assert [item["job_id"] for item in matches] == sorted([job_id, other_id])
        assert all(item["retrieval_similarity"] > 0 for item in matches)
        assert all(item["rank"] == index + 1 for index, item in enumerate(matches))
        assert fresh.scalar(select(CandidateJobMatch.score)) == 77
        assert not fresh.scalars(select(JobEmbedding).where(JobEmbedding.job_id == archived_id)).all()
        assert RetrievalService(fresh).index_profile(profile_id, fake).outcome == "unchanged"
        assert len(fake.texts) == 3
        from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION
        extra = JobEmbedding(job_id=job_id, embedding=[0.0, 1.0] + [0.0] * 382,
            model_id=MODEL_ID, model_revision="different-revision", template_version=TEMPLATE_VERSION,
            source_hash=matches[0]["job_input_hash"], taxonomy_fingerprint="x" * 64, status="ready")
        wrong_model = JobEmbedding(job_id=job_id, embedding=[0.0, 1.0] + [0.0] * 382,
            model_id="other/model", model_revision=MODEL_REVISION, template_version=TEMPLATE_VERSION,
            source_hash=matches[0]["job_input_hash"], taxonomy_fingerprint="x" * 64, status="ready")
        wrong_template = JobEmbedding(job_id=job_id, embedding=[0.0, 1.0] + [0.0] * 382,
            model_id=MODEL_ID, model_revision=MODEL_REVISION, template_version="other-template",
            source_hash=matches[0]["job_input_hash"], taxonomy_fingerprint="x" * 64, status="ready")
        fresh.add_all([extra, wrong_model, wrong_template])
        fresh.commit()
        assert len(RetrievalService(fresh).jobs_for_user(user, 20)) == 2
        selected = fresh.scalar(select(JobEmbedding).where(JobEmbedding.job_id == job_id,
            JobEmbedding.model_id == MODEL_ID, JobEmbedding.model_revision == MODEL_REVISION,
            JobEmbedding.template_version == TEMPLATE_VERSION))
        selected.status = "stale"
        fresh.commit()
        assert [row["job_id"] for row in RetrievalService(fresh).jobs_for_user(user, 20)] == [other_id]
        selected.status = "ready"
        fresh.commit()
        duplicate = JobEmbedding(job_id=job_id, embedding=[1.0] + [0.0] * 383,
            model_id=matches[0]["model_id"], model_revision=matches[0]["model_revision"],
            template_version=matches[0]["template_version"], source_hash="x" * 64,
            taxonomy_fingerprint="x" * 64, status="ready")
        fresh.add(duplicate)
        with pytest.raises(IntegrityError):
            fresh.flush()
        fresh.rollback()
    with Session(engine) as fresh:
        query = fresh.scalar(select(CandidateProfileEmbedding))
        query.status = "stale"
        fresh.commit()
    with Session(engine) as fresh:
        assert RetrievalService(fresh).index_profile(profile_id, fake).outcome == "indexed"
        fresh.commit()
    with Session(engine) as fresh:
        fresh.delete(fresh.get(Job, job_id))
        fresh.commit()
    with Session(engine) as fresh:
        assert fresh.scalar(select(JobEmbedding).where(JobEmbedding.job_id == job_id)) is None
