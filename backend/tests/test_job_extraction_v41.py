"""Job extraction v4.1: a split list item is kept only if the list vocabulary knows it."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.models import ExtractedJobTerm, Job, JobSkill
from app.nlp.job_rules_v4 import ListVocabulary, vocabulary_key
from app.nlp.skill_extractor import SkillExtractor
from app.services.job_service import JobReextractionService, retirable, retire
from app.services.section_detection_service import detect_job_segments
from tests.test_job_extraction_v4 import POSTING

VOCABULARY = ListVocabulary.build(
    dictionary=[("python", "skill"), ("terraform", "tool")],
    esco=[("stakeholder management", "skill"), ("computer science", "knowledge"), ("CI/CD pipelines", "skill")],
    tools=["Snowflake", "Looker Studio", "Chef", "Go", "embedded Linux"],
)


def _terms(text: str, vocabulary=VOCABULARY, version: str = "v4.1"):
    extractor = SkillExtractor(job_version=version, list_vocabulary=vocabulary)
    return extractor.extract_from_sections(detect_job_segments(text, version), text, "job")


def test_vocabulary_matches_normalised_labels_and_cased_tool_names():
    assert vocabulary_key("  CI/CD   Pipelines. ") == "ci cd pipelines"
    assert VOCABULARY.match("Stakeholder Management").source == "esco"
    assert VOCABULARY.match("computer science").term_type == "domain_knowledge"
    assert VOCABULARY.match("looker studio").term_type == "tool"  # multi-word: case-insensitive
    assert VOCABULARY.match("Go").source == "onet_tool"
    assert VOCABULARY.match("go") is None and VOCABULARY.match("chef") is None  # ordinary words
    assert VOCABULARY.match("TERRAFORM").source == "dictionary"  # curated: no case rule
    assert VOCABULARY.match("business masterminds") is None


def test_v41_keeps_known_list_items_and_drops_unknown_ones():
    by_name = {t.normalized_text: t for t in _terms(POSTING)}
    for name, term_type in (("snowflake", "tool"), ("stakeholder management", "skill"),
                            ("ci/cd pipelines", "skill"), ("computer science", "domain_knowledge")):
        assert by_name[name].extraction_method == "list_item@v4.1", name
        assert by_name[name].term_type == term_type, name
    # In v4 these were list items; unknown to the vocabulary, v4.1 drops them.
    v4 = {t.normalized_text for t in _terms(POSTING, version="v4") if t.extraction_method == "list_item@v4"}
    assert {"cloud platforms", "presentation skills", "gcp"} <= v4
    assert not {"cloud platforms", "presentation skills", "gcp"} & set(by_name)
    # Everything else is the v4 rule set, with v4 method strings.
    assert all(t.extraction_method.endswith("@v4") for t in _terms(POSTING) if not t.extraction_method.startswith("list_item"))
    assert ({(t.normalized_text, t.extraction_method) for t in _terms(POSTING, version="v4")
             if not t.extraction_method.startswith("list_item")}
            == {(t.normalized_text, t.extraction_method) for t in _terms(POSTING)
                if not t.extraction_method.startswith("list_item")})


def test_v41_keeps_the_precision_guards():
    text = ("Requirements\n- Python, Snowflake and Chef\n- Software\n"
            "Benefits\n- Looker Studio licence, gym membership and 30 days of paid vacation\n")
    names = {t.normalized_text for t in _terms(text, ListVocabulary.build(
        esco=[("software", "skill")], tools=["Snowflake", "Chef", "Looker Studio"]))}
    assert "snowflake" in names and "chef" in names
    assert "software" not in names  # stoplist still applies to vocabulary hits
    assert "looker studio" not in names  # benefits section is not a list section


def test_without_a_vocabulary_only_curated_dictionary_items_pass():
    extractor = SkillExtractor(job_version="v4.1")
    assert extractor.list_vocabulary.match("snowflake") is None
    assert extractor.list_vocabulary.match("python").source == "dictionary"


def test_reextraction_with_v41_retires_untouched_unknown_v4_list_items(db_session):
    text = "Requirements\n- Snowflake, business masterminds and decision-makers internally\n"
    job = Job(title="Data", company="X", location="", employment_type="", description=text, cleaned_description=text,
              status="processed", source="arbeitnow", external_id=str(uuid4()), processed_at=datetime.now(timezone.utc))
    db_session.add(job)
    db_session.commit()
    v4 = JobReextractionService(db_session, extractor=SkillExtractor(job_version="v4"))
    v4.apply(job, v4.plan(job))
    stored = set(db_session.scalars(select(ExtractedJobTerm.normalized_text).where(ExtractedJobTerm.job_id == job.id)))
    assert {"business masterminds", "decision-makers internally"} <= stored

    v41 = JobReextractionService(db_session, extractor=SkillExtractor(job_version="v4.1", list_vocabulary=VOCABULARY))
    plan = v41.plan(job)
    v41.apply(job, plan)
    items = retirable(db_session, job, plan)
    assert {term.normalized_text for term, _ in items} >= {"business masterminds", "decision-makers internally"}
    retire(db_session, job, items)
    rows = {(t.normalized_text, t.term_type, t.extraction_method) for t in db_session.scalars(
        select(ExtractedJobTerm).where(ExtractedJobTerm.job_id == job.id))}
    # A kept item at the same position is left as stored (no retire-and-re-add for a new type).
    assert ("snowflake", "skill", "list_item@v4") in rows
    assert not {name for name, _, _ in rows} & {"business masterminds", "decision-makers internally"}
    assert db_session.scalar(select(JobSkill).where(JobSkill.normalized_text == "business masterminds")) is None
