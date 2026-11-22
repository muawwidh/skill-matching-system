"""Job representations are memoized by their exact inputs; results equal a rebuild."""
from app.db.models import Job, JobSkill
from app.repositories import retrieval_repository
from app.repositories.retrieval_repository import RetrievalRepository, clear_job_representation_cache
from app.retrieval.representation import build_job_representation


def _job(db_session) -> Job:
    job = Job(title="Backend Engineer", company="Acme", location="Berlin", employment_type="Full time",
              description="Requirements\nPython\nPostgreSQL", cleaned_description="Requirements\nPython\nPostgreSQL",
              status="processed", source="manual")
    db_session.add(job)
    db_session.flush()
    db_session.add(JobSkill(job_id=job.id, raw_text="Python", normalized_text="python", skill_type="skill",
                            requirement_type="required", review_status="approved"))
    db_session.commit()
    return job


def test_cached_representation_equals_a_rebuild_and_follows_changes(db_session, monkeypatch):
    job = _job(db_session)
    repository = RetrievalRepository(db_session)
    builds = []
    real = retrieval_repository.build_job_representation
    monkeypatch.setattr(retrieval_repository, "build_job_representation",
                        lambda *args, **kwargs: builds.append(1) or real(*args, **kwargs))

    first = repository.job_input(job)
    assert repository.job_input(job) == first and len(builds) == 1  # second call is a cache hit
    clear_job_representation_cache()
    assert repository.job_input(job) == first and len(builds) == 2  # rebuilt: identical

    # Any input change is a different key: a new build with a new hash.
    job.cleaned_description += "\nDocker"
    db_session.commit()
    changed = repository.job_input(job)
    assert len(builds) == 3 and changed.source_hash != first.source_hash
    skill = db_session.query(JobSkill).filter_by(job_id=job.id).one()
    skill.review_status = "rejected"
    db_session.commit()
    assert repository.job_input(job).source_hash != changed.source_hash and len(builds) == 4


def test_cache_is_keyed_by_tokenizer(db_session):
    from tests.conftest import DeterministicTestTokenizer

    job = _job(db_session)
    a = RetrievalRepository(db_session, tokenizer=DeterministicTestTokenizer()).job_input(job)
    b = RetrievalRepository(db_session, tokenizer=DeterministicTestTokenizer()).job_input(job)
    assert a == b
    assert len(retrieval_repository._representation_cache) == 2
    assert a == build_job_representation(
        *_inputs(db_session, job), RetrievalRepository(db_session).template_version, DeterministicTestTokenizer())


def _inputs(db_session, job):
    rows = [{"id": str(s.id), "text": s.raw_text, "normalized": s.normalized_text, "type": s.skill_type,
             "requirement": s.requirement_type, "status": s.review_status, "canonical": "", "release": "",
             "term_id": ""} for s in db_session.query(JobSkill).filter_by(job_id=job.id)]
    source = {"title": job.title, "employment_type": job.employment_type, "location": job.location,
              "company": job.company, "description": job.cleaned_description, "status": job.status}
    sections = [{"id": str(s.id), "section_type": s.section_type, "heading": s.heading, "content": s.content,
                 "start_char": s.start_char, "end_char": s.end_char, "confidence_score": s.confidence_score,
                 "extraction_method": s.extraction_method} for s in job.sections]
    return source, rows, sections
