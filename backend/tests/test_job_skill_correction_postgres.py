"""Job-skill correction lifecycle in disposable PostgreSQL schemas."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.models import (ApprovedTaxonomyLink, CandidateProfile, CandidateSkill, ExtractedJobTerm,
                           Job, JobEmbedding, JobSkill, ProcessingLog, TaxonomyLinkCandidate,
                           TaxonomyVersion, User)
from app.db.models.taxonomy import TaxonomyReviewEvent
from app.repositories.retrieval_repository import RetrievalRepository
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.schemas.documents import JobSkillUpdate
from app.services.retrieval_service import RetrievalService
from app.services.skill_service import SkillService
from app.services.taxonomy_service import TaxonomyService
from test_taxonomy_postgres import pg_database  # noqa: F401
from test_retrieval import seed as seed_sqlite


class FakeEmbedder:
    def encode(self, text):
        return [1.0] + [0.0] * 383


def rows(db, model, *criteria):
    return sorted(json.dumps({column.key: getattr(row, column.key)
                              for column in inspect(row).mapper.column_attrs},
                             default=str, sort_keys=True)
                  for row in db.scalars(select(model).where(*criteria)))


def seed(db):
    actor = db.scalar(select(User).order_by(User.email))
    version = db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.status == "active"))
    taxonomy = TaxonomyRepository(db)
    python = taxonomy.add_concept(version.id, f"python-{uuid4()}", "Python canonical", "python canonical",
                                  "", "skill", "en", [], {})
    java = taxonomy.add_concept(version.id, f"java-{uuid4()}", "Java canonical", "java canonical",
                                "", "skill", "en", [], {})
    profile = CandidateProfile(user_id=actor.id, consent_to_process_cv=True)
    job = Job(title="Engineer", company="Example", location="Remote", description="Build software",
              cleaned_description="Build software", status="processed")
    other_job = Job(title="Other engineer", company="Example", description="Build software",
                    cleaned_description="Build software", status="processed")
    db.add_all([profile, job, other_job])
    db.flush()
    db.add(CandidateSkill(candidate_profile_id=profile.id, raw_text="Java", normalized_text="java",
                          review_status="approved", source="manual_review"))
    term = ExtractedJobTerm(job_id=job.id, raw_text="Python", normalized_text="python", term_type="skill",
                            extraction_method="test", evidence_sentence="Python evidence", requirement_type="required")
    other_term = ExtractedJobTerm(job_id=job.id, raw_text="SQL", normalized_text="sql", term_type="skill",
                                  extraction_method="test")
    foreign_term = ExtractedJobTerm(job_id=other_job.id, raw_text="Go", normalized_text="go", term_type="skill",
                                    extraction_method="test")
    db.add_all([term, other_term, foreign_term])
    db.flush()
    skill = JobSkill(job_id=job.id, extracted_term_id=term.id, raw_text="Python", normalized_text="python",
                     skill_type="skill", requirement_type="required", evidence_sentence="Python evidence",
                     review_status="approved")
    other_skill = JobSkill(job_id=job.id, extracted_term_id=other_term.id, raw_text="SQL", normalized_text="sql")
    foreign_skill = JobSkill(job_id=other_job.id, extracted_term_id=foreign_term.id, raw_text="Go", normalized_text="go")
    db.add_all([skill, other_skill, foreign_skill])
    db.flush()
    candidate = taxonomy.add_link_candidate("job", term.id, "Python", "python", python.id,
                                            "exact_preferred", 1.0, 1, "pending")
    alternative = taxonomy.add_link_candidate("job", term.id, "Python", "python", java.id,
                                              "fuzzy", 0.7, 2, "pending")
    db.commit()
    TaxonomyService(db).review_link(candidate.id, "approved", None, actor)
    TaxonomyService(db).review_link(alternative.id, "rejected", None, actor)
    retrieval = RetrievalService(db)
    retrieval.index_profile(profile.id, FakeEmbedder())
    retrieval.index_job(job.id, FakeEmbedder())
    retrieval.index_job(other_job.id, FakeEmbedder())
    db.commit()
    return dict(actor=actor.id, profile=profile.id, job=job.id, other_job=other_job.id,
                skill=skill.id, other_skill=other_skill.id, foreign_skill=foreign_skill.id,
                term=term.id, other_term=other_term.id, foreign_term=foreign_term.id,
                python=python.id, java=java.id)


def payload(**changes):
    return JobSkillUpdate(**({"raw_text": "Python", "normalized_text": "python", "skill_type": "skill",
                              "requirement_type": "required", "evidence_sentence": "Python evidence",
                              "review_status": "approved"} | changes))


def snapshot(db, ids):
    return {"skill": rows(db, JobSkill, JobSkill.id.in_([ids["skill"], ids["other_skill"], ids["foreign_skill"]])),
            "term": rows(db, ExtractedJobTerm, ExtractedJobTerm.id.in_([ids["term"], ids["other_term"], ids["foreign_term"]])),
            "candidate": rows(db, TaxonomyLinkCandidate, TaxonomyLinkCandidate.term_source == "job",
                              TaxonomyLinkCandidate.extracted_term_id == ids["term"]),
            "link": rows(db, ApprovedTaxonomyLink, ApprovedTaxonomyLink.term_source == "job",
                         ApprovedTaxonomyLink.extracted_term_id == ids["term"]),
            "event": rows(db, TaxonomyReviewEvent, TaxonomyReviewEvent.term_source == "job",
                          TaxonomyReviewEvent.extracted_term_id == ids["term"]),
            "embedding": rows(db, JobEmbedding, JobEmbedding.job_id.in_([ids["job"], ids["other_job"]])),
            "log": rows(db, ProcessingLog, ProcessingLog.entity_type == "job",
                        ProcessingLog.entity_id == ids["job"])}


def test_semantic_edit_clears_link_and_noop_preserves_it_sqlite(db_session):
    db = db_session
    user, _, _, _, _, job = seed_sqlite(db)
    skill = db.scalar(select(JobSkill).where(JobSkill.job_id == job.id))
    term = ExtractedJobTerm(job_id=job.id, raw_text="Python", normalized_text="python", term_type="skill",
                            extraction_method="test")
    db.add(term)
    db.flush()
    skill.extracted_term_id = term.id
    taxonomy = TaxonomyRepository(db)
    source = taxonomy.get_or_create_source("TEST", "Test", "", "")
    version = taxonomy.replace_version(source, "test", "", "test", "", True)
    concept = taxonomy.add_concept(version.id, "python", "Python canonical", "python canonical",
                                   "", "skill", "en", [], {})
    candidate = taxonomy.add_link_candidate("job", term.id, "Python", "python", concept.id,
                                            "exact_preferred", 1.0, 1, "pending")
    db.commit()
    TaxonomyService(db).review_link(candidate.id, "approved", None, user)
    assert RetrievalService(db).index_job(job.id, FakeEmbedder()).outcome == "indexed"
    db.commit()
    assert "Python canonical" in RetrievalRepository(db).job_input(job).text
    SkillService(db).update_job_skill(job.id, skill.id, payload(raw_text="Java", normalized_text="java"))
    assert taxonomy.selected_link("job", term.id) is None
    assert taxonomy.term_candidates("job", term.id) == []
    assert db.get(ExtractedJobTerm, term.id).raw_text == "Java"
    assert "Python canonical" not in RetrievalRepository(db).job_input(job).text
    assert db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == job.id)).status == "stale"
    assert len(taxonomy.review_history("job", term.id, 20, 0)) == 1


def test_semantic_correction_clears_only_its_identity_and_reindexes_after_review(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        ids = seed(db)
        before = snapshot(db, ids)
        assert "Python canonical" in RetrievalRepository(db).job_input(db.get(Job, ids["job"])).text
        assert ids["job"] in [item["job_id"] for item in RetrievalService(db).jobs_for_user(db.get(User, ids["actor"]), 20)]
        SkillService(db).update_job_skill(ids["job"], ids["skill"], payload(raw_text="Java", normalized_text="JAVA"))
    with Session(engine) as db:
        after = snapshot(db, ids)
        assert after["candidate"] == after["link"] == []
        assert after["event"] == before["event"] and len(after["event"]) == 2
        skill = db.get(JobSkill, ids["skill"])
        term = db.get(ExtractedJobTerm, ids["term"])
        assert (skill.raw_text, skill.normalized_text, skill.skill_type) == (term.raw_text, term.normalized_text, term.term_type) == ("Java", "java", "skill")
        assert skill.review_status == "approved"
        assert after["embedding"] != before["embedding"]
        assert db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == ids["job"])).status == "stale"
        assert rows(db, JobSkill, JobSkill.id.in_([ids["other_skill"], ids["foreign_skill"]])) == [
            item for item in before["skill"] if json.loads(item)["id"] != str(ids["skill"])]
        assert rows(db, ExtractedJobTerm, ExtractedJobTerm.id.in_([ids["other_term"], ids["foreign_term"]])) == [
            item for item in before["term"] if json.loads(item)["id"] != str(ids["term"])]
        assert db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == ids["other_job"])).status == "ready"
        value = RetrievalRepository(db).job_input(db.get(Job, ids["job"]))
        assert "Java" in value.text and "Python canonical" not in value.text
        assert ids["job"] not in [item["job_id"] for item in RetrievalService(db).jobs_for_user(db.get(User, ids["actor"]), 20)]
        assert TaxonomyRepository(db).selected_link("job", ids["term"]) is None
        assert TaxonomyRepository(db).term_candidates("job", ids["term"]) == []
        replacement = TaxonomyRepository(db).add_link_candidate("job", ids["term"], "Java", "java",
                                                                 ids["java"], "human_correction", 1.0, 1, "pending")
        db.commit()
        TaxonomyService(db).review_link(replacement.id, "approved", None, db.get(User, ids["actor"]))
        assert RetrievalService(db).index_job(ids["job"], FakeEmbedder()).outcome == "indexed"
        db.commit()
    with Session(engine) as db:
        assert "Java canonical" in RetrievalRepository(db).job_input(db.get(Job, ids["job"])).text
        assert "Python canonical" not in RetrievalRepository(db).job_input(db.get(Job, ids["job"])).text
        assert ids["job"] in [item["job_id"] for item in RetrievalService(db).jobs_for_user(db.get(User, ids["actor"]), 20)]


@pytest.mark.parametrize("changes,semantic", [
    ({"raw_text": "Java"}, True),
    ({"normalized_text": "java"}, True),
    ({"skill_type": "tool"}, True),
    ({"evidence_sentence": "New evidence"}, False),
    ({"requirement_type": "preferred"}, False),
    ({"review_status": "rejected"}, False),
    ({}, False),
])
def test_edit_classification_mapping_and_noop(pg_database, changes, semantic):
    engine, _, _ = pg_database
    with Session(engine) as db:
        ids = seed(db)
        before = snapshot(db, ids)
        SkillService(db).update_job_skill(ids["job"], ids["skill"], payload(**changes))
    with Session(engine) as db:
        after = snapshot(db, ids)
        assert after["event"] == before["event"]
        if not changes:
            assert after == before
        else:
            assert db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == ids["job"])).status == "stale"
            assert db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == ids["other_job"])).status == "ready"
            if semantic:
                assert after["candidate"] == after["link"] == []
                term = db.get(ExtractedJobTerm, ids["term"])
                skill = db.get(JobSkill, ids["skill"])
                assert (term.raw_text, term.normalized_text, term.term_type) == (
                    skill.raw_text, skill.normalized_text, skill.skill_type)
            else:
                assert after["candidate"] == before["candidate"]
                assert after["link"] == before["link"]
                if "review_status" in changes:
                    assert "Python canonical" not in RetrievalRepository(db).job_input(db.get(Job, ids["job"])).text


def test_semantic_edit_rolls_back_all_rows_after_invalidation(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        ids = seed(db)
        before = snapshot(db, ids)
    original = RetrievalRepository.invalidate_job

    def fail_after_staling(self, job_id):
        original(self, job_id)
        raise RuntimeError("injected after writes")

    monkeypatch.setattr(RetrievalRepository, "invalidate_job", fail_after_staling)
    with Session(engine) as db:
        with pytest.raises(RuntimeError, match="injected after writes"):
            SkillService(db).update_job_skill(ids["job"], ids["skill"], payload(raw_text="Java", normalized_text="java"))
        db.rollback()
    with Session(engine) as db:
        assert snapshot(db, ids) == before
