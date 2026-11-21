"""Live-job link suggestions are kept but not listed in the staff review queue by default (D057)."""
from uuid import uuid4

from sqlalchemy import func, select

from app.db.models import ExtractedJobTerm, Job, TaxonomyLinkCandidate
from app.repositories.taxonomy_repository import TaxonomyRepository
from tests.test_taxonomy import grant_researcher, register


def _job_term(db, source, text):
    job = Job(title=f"{source} role", description="x", cleaned_description="x", status="processed", source=source,
              external_id=None if source in {"manual", "evaluation"} else f"{source}-1")
    db.add(job)
    db.flush()
    term = ExtractedJobTerm(job_id=job.id, raw_text=text, normalized_text=text.lower(), term_type="skill",
                            extraction_method="dictionary@v3")
    db.add(term)
    db.flush()
    return term.id


def test_review_queue_defaults_to_cv_manual_and_evaluation_terms(client, db_session):
    headers = {"Authorization": f"Bearer {register(client)}"}
    grant_researcher(db_session)
    assert client.post("/taxonomy/import/sample", headers=headers).status_code == 200
    repository = TaxonomyRepository(db_session)
    concept = repository.active_concepts()[0]
    terms = {"cv": ("candidate", uuid4(), "Cv skill"),
             "manual": ("job", _job_term(db_session, "manual", "Manual skill"), "Manual skill"),
             "evaluation": ("job", _job_term(db_session, "evaluation", "Evaluation skill"), "Evaluation skill"),
             "live": ("job", _job_term(db_session, "arbeitnow", "Live skill"), "Live skill")}
    for term_source, term_id, text in terms.values():
        repository.add_link_candidate(term_source=term_source, extracted_term_id=term_id, raw_text=text,
                                      normalized_text=text.lower(), concept_id=concept.id, match_method="fuzzy",
                                      confidence_score=0.8, rank=1, review_status="pending")
    db_session.commit()

    def listed(path):
        body = client.get(path, headers=headers).json()
        items = body["items"] if isinstance(body, dict) else body
        return {item["raw_text"] for item in items}

    everything = {"Cv skill", "Manual skill", "Evaluation skill", "Live skill"}
    for base in ("/taxonomy/reviews?state=pending", "/admin/mappings/review?x=1"):
        assert listed(base) == everything - {"Live skill"}
        assert listed(base + "&scope=default") == everything - {"Live skill"}
        assert listed(base + "&scope=live") == {"Live skill"}
        assert listed(base + "&scope=all") == everything
    assert client.get("/taxonomy/reviews?scope=other", headers=headers).status_code == 422
    # A lookup by term ID finds a live-job term from the default view.
    live_id = terms["live"][1]
    assert listed(f"/taxonomy/reviews?state=all&q={live_id}") == {"Live skill"}
    # Only live-job terms are flagged; the UI shows their pending suggestions as "automatic".
    body = client.get("/taxonomy/reviews?state=pending&scope=all", headers=headers).json()
    assert {item["raw_text"]: item["live_job"] for item in body["items"]} == {
        "Cv skill": False, "Manual skill": False, "Evaluation skill": False, "Live skill": True}
    assert {c["review_status"] for item in body["items"] for c in item["candidates"]} == {"pending"}  # data unchanged
    # Nothing was deleted.
    assert db_session.scalar(select(func.count()).select_from(TaxonomyLinkCandidate)) == 4
