"""Job extraction contract v4: list splitting, precision guards, language and certification
rules, acronym-safe linking, and the re-extraction safeguards. CV extraction is unchanged."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models import ExtractedJobTerm, Job, JobSkill
from app.db.models.taxonomy import TaxonomyReviewEvent
from app.nlp import job_rules_v4 as rules
from app.nlp.skill_extractor import SkillExtractor
from app.services.matching_service import SkillItem, compute_coverage
from app.services.section_detection_service import SectionDetectionService, detect_job_segments
from app.taxonomy.concept_index import ConceptIndex, IndexedConcept

POSTING = """About Example GmbH
We are a leading provider of Kubernetes tooling with offices in Berlin. We love SQL.

Requirements
- Strong knowledge of Python, Terraform and Snowflake
- 5 years of professional, hands-on software engineering experience
- Experience with cloud platforms (e.g. AWS, GCP) and CI/CD pipelines
- Excellent stakeholder management and presentation skills
- Knowledge of Artificial Intelligence (AI)
- Fluent English; German is a plus
- Master's degree in Computer Science or a related field
- IT, SaaS and certification
Nice to have
- AWS Certified Solutions Architect or TOGAF certification
- Experience as a Scrum Master
Privacy Notice
We process your personal data with Workday.
"""


def _terms(text: str, version: str = "v4"):
    extractor = SkillExtractor(job_version=version)
    return extractor.extract_from_sections(detect_job_segments(text, version), text, "job")


def test_v4_splits_lists_in_requirement_sections_and_keeps_offsets() -> None:
    terms = _terms(POSTING)
    by_name = {term.normalized_text: term for term in terms}
    for name in ("terraform", "snowflake", "cloud platforms", "gcp", "ci/cd pipelines", "stakeholder management",
                 "presentation skills", "artificial intelligence", "computer science"):
        assert by_name[name].extraction_method == "list_item@v4", name
        assert by_name[name].term_type == "skill"
    assert by_name["terraform"].requirement_type == "required"
    # Covered by the curated dictionary: not added again as a list item.
    assert by_name["python"].extraction_method == "dictionary@v4"
    assert sum(term.normalized_text == "python" for term in terms) == 1
    assert all(POSTING[term.start_char:term.end_char] == term.raw_text for term in terms)
    assert all(term.extraction_method.endswith("@v4") for term in terms)


def test_v4_guards_drop_generic_terms_and_company_and_privacy_text() -> None:
    names = {term.normalized_text for term in _terms(POSTING)}
    assert not names & {"it", "saas", "certification", "related field", "a related field"}
    # "About <Company>" and privacy headings are not extracted at all.
    assert "kubernetes" not in names and "workday" not in names
    assert "sql" not in names
    # Without headings, a sentence about the company is skipped but a requirement sentence is not.
    text = "We are a fast-growing SaaS company using Docker. You know Git well."
    assert {term.normalized_text for term in _terms(text)} == {"git"}


def test_v4_languages_need_a_cue_and_are_not_assessed() -> None:
    terms = _terms(POSTING)
    languages = {term.normalized_text: term for term in terms if term.term_type == "language"}
    assert set(languages) == {"english", "german"}
    assert languages["english"].extraction_method == "language_rule@v4"
    assert rules.language_terms("We sell to the German market.") == []
    candidate = [SkillItem("english", "language")]
    job = [SkillItem("english", "language", requirement="required"), SkillItem("git", "tool", requirement="required")]
    result = compute_coverage(candidate, job)
    assert result.not_assessed_required == ["english"]
    assert [entry["label"] for entry in result.missing_required] == ["git"]


def test_v4_names_certifications_instead_of_the_bare_word() -> None:
    certifications = {term.normalized_text for term in _terms(POSTING) if term.term_type == "certification"}
    assert certifications == {"aws certified solutions architect", "togaf certification"}
    assert [s.normalized for s in rules.certification_terms("PMP and Lean Six Sigma Green Belt required")] == [
        "pmp", "lean six sigma green belt"]
    assert rules.certification_terms("Relevant certification is a plus.") == []


def test_v4_experience_and_qualification_patterns() -> None:
    names = {term.normalized_text for term in _terms(POSTING)}
    assert "5 years of professional, hands-on software engineering experience" in names
    assert "master's degree" in names and "master" not in names  # "Scrum Master" is not a degree
    text = "Requirements\n- Five years' relevant experience\n- Experience of at least 3 years in sales"
    experience = {t.normalized_text for t in _terms(text) if t.term_type == "experience_indicator"}
    assert experience == {"five years' relevant experience", "experience of at least 3 years"}


def test_v3_output_is_unchanged_by_the_v4_rules() -> None:
    methods = {term.extraction_method for term in _terms(POSTING, "v3")}
    assert methods <= {"dictionary@v3", "regex@v3"}
    assert "certification" in {term.normalized_text for term in _terms(POSTING, "v3")}


def test_cv_extraction_does_not_depend_on_the_job_version() -> None:
    text = "Skills\nPython, Terraform and Snowflake. Fluent English. IT support. 5 years experience"
    sections = SectionDetectionService().detect(text)
    v3 = SkillExtractor(job_version="v3").extract_from_sections(sections, text, "candidate")
    v4 = SkillExtractor(job_version="v4").extract_from_sections(sections, text, "candidate")
    assert v3 == v4 and all(term.extraction_method.endswith("@v2") for term in v4)


def test_unknown_job_version_is_rejected() -> None:
    with pytest.raises(ValueError):
        SkillExtractor(job_version="v9")


def test_acronyms_link_only_to_labels_spelled_the_same() -> None:
    version = uuid4()
    gtm = IndexedConcept(uuid4(), version, "GTM", "gtm")
    go_to_market = IndexedConcept(uuid4(), version, "go-to-market strategy", "go-to-market strategy")
    lowercase = IndexedConcept(uuid4(), version, "gtm planning", "gtm planning")
    index = ConceptIndex([gtm, go_to_market, lowercase], {go_to_market.id: {"gtm"}},
                         acronym_labels={go_to_market.id: {"GTM"}})
    assert [r.concept.id for r in index.rank_acronym("GTM")] == [gtm.id, go_to_market.id]
    assert index.rank_acronym("Gtm") == []
    assert rules.is_short_acronym("GTM") and rules.is_short_acronym("B2B") and not rules.is_short_acronym("SaaS")

    from app.services.taxonomy_service import _acronym_safe

    term = lambda raw, method: ExtractedJobTerm(raw_text=raw, extraction_method=method)
    assert _acronym_safe(term("GTM", "list_item@v4"))
    assert not _acronym_safe(term("SQL", "dictionary@v4"))  # curated dictionary terms link as before
    assert not _acronym_safe(term("GTM", "esco_vocabulary@v3:ESCO-1.2.1:o7"))  # earlier versions unchanged


def test_acronym_links_are_never_approved_automatically(db_session) -> None:
    from app.db.models import TaxonomyConcept, TaxonomySource, TaxonomyVersion
    from app.repositories.document_repository import DocumentRepository
    from app.services.taxonomy_service import TaxonomyService
    from app.nlp.skill_extractor import ExtractedTerm
    from app.taxonomy.concept_index import clear_concept_index_cache

    source = TaxonomySource(code="ESCO", name="ESCO")
    release = TaxonomyVersion(source=source, version="9.9", status="active", imported_at=datetime.now(timezone.utc))
    db_session.add_all([source, release])
    db_session.flush()
    for label in ("GTM", "SQL"):
        db_session.add(TaxonomyConcept(taxonomy_version_id=release.id, external_id=f"x:{label}", preferred_label=label,
                                       normalized_label=label.lower(), concept_type="skill"))
    job = Job(title="Sales", description="x", cleaned_description="x", status="processed", source="greenhouse")
    db_session.add(job)
    db_session.commit()
    clear_concept_index_cache()
    make = lambda raw, method: ExtractedTerm(raw, raw.lower(), "skill", "required_skills", raw, method, 0.6, 0, 3,
                                             "required")
    DocumentRepository(db_session).add_job_terms(job, [make("GTM", "list_item@v4"), make("SQL", "dictionary@v4")])
    db_session.commit()
    result = TaxonomyService(db_session).link_document("job", job.id)
    clear_concept_index_cache()
    assert result.links_auto_approved == 1  # SQL only; the GTM link stays for review


# ---- Re-extraction safeguards --------------------------------------------------------------

def _live_job(db_session, description: str, source: str = "greenhouse") -> Job:
    from app.services.job_service import JobService

    job = Job(title="Engineer", description=description, cleaned_description=description, status="draft",
              source=source)
    db_session.add(job)
    db_session.flush()
    JobService(db_session)._process_existing_job(job)
    db_session.commit()
    return job


def test_retire_removes_only_untouched_items_of_live_jobs(db_session, monkeypatch) -> None:
    from app.services.job_service import JobReextractionService, retirable, retire

    monkeypatch.setattr(settings, "JOB_EXTRACTION_VERSION", "v3")
    description = "Requirements\n- Python\n- Docker certification\n- Scrum Master experience"
    live = _live_job(db_session, description)
    manual = _live_job(db_session, description, source="manual")
    skills = {s.normalized_text: s for s in db_session.scalars(select(JobSkill).where(JobSkill.job_id == live.id))}
    assert {"master", "certification"} <= set(skills)
    # A person reviewed the link of "master": that item is kept.
    db_session.add(TaxonomyReviewEvent(term_source="job", extracted_term_id=skills["master"].extracted_term_id,
                                       candidate_id=uuid4(), action="reject", created_at=live.created_at,
                                       before_state={}, after_state={}))
    db_session.commit()

    service = JobReextractionService(db_session, use_esco_vocabulary=False, version="v4")
    plan = service.plan(live)
    vanished = {term.normalized_text for term, _ in plan.vanished}
    assert {"master", "certification"} <= vanished
    items = retirable(db_session, live, plan)
    assert {term.normalized_text for term, _ in items} == vanished - {"master"}
    assert retirable(db_session, manual, service.plan(manual)) == []
    service.apply(live, plan)
    assert retire(db_session, live, items) == len(items)
    names = set(db_session.scalars(select(JobSkill.normalized_text).where(JobSkill.job_id == live.id)))
    assert "certification" not in names and "master" in names and "python" in names
    assert "docker certification" in names


def test_reextract_cli_never_touches_evaluation_jobs(db_session, monkeypatch, capsys) -> None:
    from app.services import job_service

    evaluation = _live_job(db_session, "Requirements\n- Python, Terraform", source="evaluation")
    before = set(db_session.scalars(select(ExtractedJobTerm.id).where(ExtractedJobTerm.job_id == evaluation.id)))
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db_session)
    assert job_service.main(["reextract", "--apply", "--esco", "off", "--sources", "all",
                             "--job", str(evaluation.id)]) == 0
    assert "0 jobs (1 evaluation/non-live skipped)" in capsys.readouterr().out
    assert set(db_session.scalars(select(ExtractedJobTerm.id).where(ExtractedJobTerm.job_id == evaluation.id))) == before


def test_processed_evaluation_jobs_cannot_be_reprocessed(db_session) -> None:
    from fastapi import HTTPException
    from app.services.job_service import JobService

    evaluation = _live_job(db_session, "Requirements\n- Python", source="evaluation")
    with pytest.raises(HTTPException) as error:
        JobService(db_session).process_job(evaluation.id)
    assert error.value.status_code == 409


def test_config_switch_selects_the_job_rules(db_session, monkeypatch) -> None:
    from app.services.job_service import build_job_extractor

    assert build_job_extractor(db_session, use_esco_vocabulary=False).job_version == "v4"
    monkeypatch.setattr(settings, "JOB_EXTRACTION_VERSION", "v3")
    assert build_job_extractor(db_session, use_esco_vocabulary=False).job_version == "v3"
    job = _live_job(db_session, "Requirements\n- Terraform and Snowflake")
    assert set(db_session.scalars(select(ExtractedJobTerm.extraction_method).where(
        ExtractedJobTerm.job_id == job.id))) <= {"dictionary@v3", "regex@v3"}


def test_list_items_skip_prose_eeo_benefits_contacts_and_fragments() -> None:
    text = """Requirements
- Experience with Terraform, Snowflake and dbt
We value delivering projects for government, public sector organisations and charities.
We are an equal opportunity employer and do not discriminate on the basis of race, religion, sex, age or veteran status.
- Comprehensive medical, dental and vision plans, unlimited PTO and a home office stipend
- Must be a U.S. citizen, U.S. national or permanent resident
- Contact: Mr. Max Example, Musterstrasse 107, max@example.com
- Excellent written and spoken English
- Experience with"""
    names = {span.normalized for span in rules.list_items(text)}
    assert names == {"terraform", "snowflake", "dbt"}
    terms = {term.normalized_text for term in _terms(text)}
    assert not terms & {"religion", "age", "sex", "dental", "pto", "written", "spoken", "government"}
    assert "english" in terms
