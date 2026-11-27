import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone
from uuid import UUID

from app.core.config import settings
from app.db.models import (
    ExtractedCandidateTerm,
    ExtractedJobTerm,
    JobSkill,
    Role,
    TaxonomyConcept,
    TaxonomyLabel,
    TaxonomySource,
    TaxonomyVersion,
    User,
)
from app.nlp.skill_extractor import (
    ESCO_DIGITAL_SCHEME,
    EXTRACTION_CONTRACT_VERSION,
    JOB_EXTRACTION_CONTRACT_VERSION,
    EscoConceptLabels,
    EscoVocabulary,
    SkillDictionary,
    SkillDictionaryEntry,
    SkillExtractor,
)
from app.services.job_service import build_job_extractor
from app.services.section_detection_service import SectionDetectionService, classify_job_heading, detect_job_segments


@pytest.fixture
def v3_jobs(monkeypatch):
    """Tests of job extraction contract v3 behaviour (v4 is the default)."""
    monkeypatch.setattr(settings, "JOB_EXTRACTION_VERSION", "v3")


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "skills@example.com",
            "full_name": "Skill Reviewer",
            "password": "correct-horse-password",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def job_manager_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "job-manager@example.com",
            "full_name": "Synthetic Job Manager",
            "password": "correct-horse-password",
        },
    )
    assert response.status_code == 201
    user = db_session.scalar(select(User).where(User.email == "job-manager@example.com"))
    assert user is not None
    user.roles.append(Role(name="admin", description="Job management"))
    db_session.commit()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_skill_extractor_finds_dictionary_and_regex_terms() -> None:
    text = "Skills\nPython, FastAPI, SQL\n\nExperience\n5 years experience building REST APIs"
    sections = SectionDetectionService().detect(text)
    terms = SkillExtractor().extract_from_sections(sections, text, "candidate")
    normalized_terms = {term.normalized_text for term in terms}
    term_types = {term.term_type for term in terms}
    assert {"python", "fastapi", "sql", "rest api"} <= normalized_terms
    assert "experience_indicator" in term_types
    assert all(term.evidence_sentence for term in terms)


def test_skill_extractor_trims_evidence_from_dense_skill_lists() -> None:
    text = (
        "Skills\n"
        "Python, FastAPI • REST API Development • OpenAI API integration • "
        "Prompt Engineering • Git & GitHub • API Testing (Postman)"
    )
    sections = SectionDetectionService().detect(text)
    terms = SkillExtractor().extract_from_sections(sections, text, "candidate")
    by_name = {term.normalized_text: term.evidence_sentence for term in terms}

    assert by_name["python"] == "Python"
    assert by_name["fastapi"] == "FastAPI"
    assert by_name["git"] == "Git & GitHub"
    assert len(by_name["python"]) < 30


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Experience with SQL.", {"sql"}),
        ("Used Docker, Git, and Python.", {"docker", "git", "python"}),
        ("Skills include FastAPI; PostgreSQL: advanced.", {"fastapi", "postgresql"}),
        ("Built systems with React!", {"react"}),
        ("Worked with Java?", {"java"}),
        ("Used PYTHON", {"python"}),
        ("Used Python)", {"python"}),
    ],
)
def test_dictionary_punctuation_and_case_preserve_offsets_and_evidence(text: str, expected: set[str]) -> None:
    extractor = SkillExtractor()
    extractor.spacy_nlp = None
    extractor.spacy_matcher = None
    terms = extractor.extract_from_sections(SectionDetectionService().detect(text), text, "candidate")
    dictionary_terms = [term for term in terms if term.extraction_method.startswith("dictionary@")]
    assert {term.normalized_text for term in dictionary_terms} == expected
    for term in dictionary_terms:
        assert text[term.start_char : term.end_char] == term.raw_text
        assert term.raw_text.lower() in term.evidence_sentence.lower()
        assert term.extraction_method == f"dictionary@{EXTRACTION_CONTRACT_VERSION}"


def test_dictionary_boundaries_protect_technical_names_and_substrings() -> None:
    dictionary = SkillDictionary(
        [
            SkillDictionaryEntry(label=name, term_type="skill", aliases=(name.lower(),))
            for name in ("C++", "C#", ".NET", "Node.js", "Java", "TypeScript", "React")
        ]
    )
    extractor = SkillExtractor(dictionary)
    extractor.spacy_nlp = None
    extractor.spacy_matcher = None
    text = "C++ C# .NET Node.js Java TypeScript; reactive javascript typescriptish C++Plus Node.jsx"
    terms = extractor.extract_from_sections(SectionDetectionService().detect(text), text, "candidate")
    assert {term.normalized_text for term in terms} == {
        "c++", "c#", ".net", "node.js", "java", "typescript"
    }
    assert all(text[term.start_char : term.end_char] == term.raw_text for term in terms)


def test_dictionary_dotted_identifier_boundary_requires_complete_skill_token() -> None:
    dictionary = SkillDictionary(
        [
            SkillDictionaryEntry(label="Python", term_type="skill", aliases=("python",)),
            SkillDictionaryEntry(label="Node.js", term_type="tool", aliases=("node.js",)),
        ]
    )
    extractor = SkillExtractor(dictionary)
    extractor.spacy_nlp = None
    extractor.spacy_matcher = None
    text = "Python.org Python. Node.js Node.js.example"
    terms = extractor.extract_from_sections(SectionDetectionService().detect(text), text, "candidate")
    assert [(term.normalized_text, term.raw_text, term.start_char, term.end_char) for term in terms] == [
        ("python", "Python", text.index("Python. "), text.index("Python. ") + len("Python")),
        ("node.js", "Node.js", text.index("Node.js "), text.index("Node.js ") + len("Node.js")),
    ]
    assert all(term.extraction_method == "dictionary@v2" for term in terms)


def test_optional_spacy_method_keeps_distinct_versioned_provenance() -> None:
    class FakeSpan:
        text = "Python"
        start_char = 0
        end_char = 6

    class FakeDocument:
        def __getitem__(self, item):
            return FakeSpan()

    class FakeNlp:
        vocab = type("Vocab", (), {"strings": {1: "Python::skill"}})()

        def __call__(self, text):
            return FakeDocument()

    extractor = SkillExtractor()
    extractor.spacy_nlp = FakeNlp()
    extractor.spacy_matcher = lambda document: [(1, 0, 1)]
    terms = extractor.extract_from_sections(SectionDetectionService().detect("Python"), "Python", "candidate")
    assert len(terms) == 1
    assert terms[0].extraction_method == "spacy_phrase_matcher@v2"
    assert (terms[0].raw_text, terms[0].start_char, terms[0].end_char) == ("Python", 0, 6)


@pytest.mark.usefixtures("v3_jobs")
def test_versioned_extraction_methods_are_persisted_for_candidate_and_job(
    client: TestClient, db_session: Session
) -> None:
    assert (EXTRACTION_CONTRACT_VERSION, JOB_EXTRACTION_CONTRACT_VERSION) == ("v2", "v3")
    headers = auth_headers(client)
    cv = client.post(
        "/cvs/paste",
        headers=headers,
        json={"text": "Skills: Python. 5 years experience", "original_filename": "version.txt", "consent_to_process": True},
    )
    assert cv.status_code == 201
    job = client.post(
        "/jobs",
        headers=job_manager_headers(client, db_session),
        json={
            "title": "Engineer", "company": "Example", "location": "Remote",
            "employment_type": "Full-time", "description": "Required skills: SQL. 3 years experience",
        },
    )
    assert job.status_code == 201
    candidate_methods = set(db_session.scalars(select(ExtractedCandidateTerm.extraction_method)))
    job_methods = set(db_session.scalars(select(ExtractedJobTerm.extraction_method)))
    # CV extraction keeps contract v2; job extraction moved to v3.
    assert {"dictionary@v2", "regex@v2"} <= candidate_methods
    assert not any(method.endswith("@v3") for method in candidate_methods)
    assert {"dictionary@v3", "regex@v3"} <= job_methods
    assert not any("@v2" in method for method in job_methods)


def test_cv_processing_extracts_and_reviews_candidate_skills(client: TestClient) -> None:
    headers = auth_headers(client)
    cv_response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Summary\nBackend engineer\n\nSkills\nPython\nFastAPI\nSQL",
            "original_filename": "skills-cv.txt",
            "consent_to_process": True,
        },
    )
    assert cv_response.status_code == 201
    cv_id = cv_response.json()["id"]

    skills_response = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers)
    assert skills_response.status_code == 200
    skills = skills_response.json()
    assert {skill["normalized_text"] for skill in skills} >= {"python", "fastapi", "sql"}

    first_skill = skills[0]
    first_skill["review_status"] = "approved"
    first_skill["raw_text"] = "Python 3"
    first_skill["normalized_text"] = "python 3"
    review_response = client.put(
        f"/cvs/{cv_id}/extracted-skills",
        headers=headers,
        json={"skills": skills},
    )
    assert review_response.status_code == 200
    assert any(skill["normalized_text"] == "python 3" for skill in review_response.json())


def test_job_processing_extracts_requirement_skills(client: TestClient, db_session: Session) -> None:
    headers = job_manager_headers(client, db_session)
    job_response = client.post(
        "/jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Required skills\nPython\nDocker\n\nPreferred skills\nKubernetes\nCI/CD",
        },
    )
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    skills_response = client.get(f"/jobs/{job_id}/extracted-skills", headers=headers)
    assert skills_response.status_code == 200
    skills = skills_response.json()
    by_name = {skill["normalized_text"]: skill["requirement_type"] for skill in skills}
    assert by_name["python"] == "required"
    assert by_name["docker"] == "required"
    assert by_name["kubernetes"] == "preferred"
    sections = {skill["normalized_text"]: skill["source_section"] for skill in skills}
    assert sections["python"] == "required_skills" and sections["kubernetes"] == "preferred_skills"
    assert all("occurrences" not in skill and "taxonomy" not in skill for skill in skills)
    target = skills[0]
    target["review_status"] = "rejected"
    updated = client.put(f"/jobs/{job_id}/extracted-skills/{target['id']}", headers=headers, json=target)
    assert updated.status_code == 200
    assert updated.json()["id"] == target["id"]
    assert updated.json()["review_status"] == "rejected"
    assert updated.json()["requirement_type"] == target["requirement_type"]


def test_matching_reports_coverage_counts_from_approved_skills(
        client: TestClient, db_session: Session, fake_retrieval) -> None:
    headers = auth_headers(client)
    manager = job_manager_headers(client, db_session)
    cv_response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Summary\nBackend engineer\n\nSkills\nPython\nFastAPI",
            "original_filename": "matching-cv.txt",
            "consent_to_process": True,
        },
    )
    assert cv_response.status_code == 201
    cv_id = cv_response.json()["id"]

    job_response = client.post(
        "/jobs",
        headers=manager,
        json={
            "title": "API Engineer",
            "company": "Acme",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Required skills\nPython\nDocker\nBachelor's degree\n\nPreferred skills\nFastAPI",
        },
    )
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    # Pending CV skills are never used: there is no matching profile to retrieve with yet.
    pending = client.get("/matches/recommendations", headers=headers).json()
    assert pending["status"] == "no_approved_skills" and pending["results"] == []
    assert "Approve at least one skill" in pending["message"]

    cv_skills = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()
    for skill in cv_skills:
        skill["review_status"] = "approved"
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": cv_skills}).status_code == 200
    for skill in client.get(f"/jobs/{job_id}/extracted-skills", headers=manager).json():
        skill["review_status"] = "approved"
        assert client.put(f"/jobs/{job_id}/extracted-skills/{skill['id']}", headers=manager, json=skill).status_code == 200

    # GET recomputes, so approvals are reflected without an explicit refresh.
    recommendations = client.get("/matches/recommendations", headers=headers).json()
    assert recommendations["status"] == "ready" and recommendations["message"] == ""
    assert recommendations["top_n"] == settings.RECOMMENDATION_TOP_N
    assert recommendations["active_jobs"] == 1 and recommendations["unindexed_jobs"] == 0
    assert len(recommendations["results"]) == 1
    recommendation = recommendations["results"][0]
    assert recommendation["rank"] == 1 and recommendation["job_id"] == job_id
    assert recommendation["matched_required"] == [{"label": "python", "matched_via": "skill_name", "reviewed": True, "esco_area": None}]
    assert recommendation["matched_preferred"] == [{"label": "fastapi", "matched_via": "skill_name", "reviewed": True, "esco_area": None}]
    # Docker has no approved taxonomy link and no same-name CV skill: missing, checked by name only.
    assert recommendation["missing_required"] == [{"label": "docker", "checked_via": "skill_name", "reviewed": True, "esco_area": None}]
    assert recommendation["missing_preferred"] == []
    assert "score" not in recommendation and "retrieval_similarity" not in recommendation
    assert recommendation["job_skill_count"] == 3
    explanation = recommendation["explanation"].splitlines()
    assert explanation[0] == "Required skills: 1 of 2 matched (python); missing: docker."
    assert explanation[1] == "Preferred skills: 1 of 1 matched (fastapi)."
    assert explanation[2] == ("Checked by name only (may appear in your CV under a different wording): docker.")
    assert "could not be compared" not in recommendation["explanation"]
    assert explanation[3] == "Also required — not assessed by the system: bachelor's degree."
    assert "%" not in recommendation["explanation"]
    assert recommendation["job"]["title"] == "API Engineer"

    refreshed = client.post("/matches/recommendations/refresh", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["results"][0]["matched_required"] == recommendation["matched_required"]


def _item(name, concept=None, requirement="", skill_type="skill"):
    from app.services.matching_service import SkillItem

    return SkillItem(name=name, skill_type=skill_type, concept_id=concept,
                     concept_label=f"{name} (concept)" if concept else None, requirement=requirement)


def test_coverage_prefers_concepts_and_falls_back_to_names_only_when_not_both_linked() -> None:
    from uuid import uuid4

    from app.services.matching_service import compute_coverage

    python, java, docker, git = uuid4(), uuid4(), uuid4(), uuid4()
    candidate = [
        _item("python3", python),          # different name, same concept
        _item("java", uuid4()),            # same name, different concept
        _item("docker"),                   # unlinked, same name as a linked job skill
        _item("excel"),                    # unlinked, same name as an unlinked job skill
    ]
    job = [
        _item("python", python, "required"),
        _item("java", java, "required"),
        _item("docker", docker, "required"),
        _item("git", git, "required"),
        _item("excel", None, "unknown"),
        _item("rust", None, "required"),
    ]
    result = compute_coverage(candidate, job)
    assert result.matched_required == [
        {"label": "docker (concept)", "matched_via": "skill_name"},
        {"label": "python (concept)", "matched_via": "taxonomy_concept"},
    ]
    # Both linked to different concepts: no name fallback, so Java is missing.
    # An unlinked job skill without a same-name CV skill is missing, checked by name only.
    assert result.missing_required == [
        {"label": "git (concept)", "checked_via": "taxonomy_concept"},
        {"label": "java (concept)", "checked_via": "taxonomy_concept"},
        {"label": "rust", "checked_via": "skill_name"},
    ]
    # `unknown` counts as preferred.
    assert result.matched_preferred == [{"label": "excel", "matched_via": "skill_name"}]
    assert not hasattr(result, "not_compared")
    assert (result.required_total, result.preferred_total) == (5, 1)


def test_coverage_deduplicates_and_lists_non_skill_terms_without_scoring() -> None:
    from uuid import uuid4

    from app.services.matching_service import compute_coverage

    sql = uuid4()
    job = [
        _item("sql", sql, "preferred"),
        _item("sql", sql, "required"),            # same concept listed twice: required wins
        _item("sql", None, "unknown"),            # unlinked duplicate joins the concept group
        _item("bachelor's degree", None, "required", "qualification"),
        _item("3 years experience", None, "unknown", "experience_indicator"),
        _item("aws certified", None, "preferred", "certification"),
    ]
    result = compute_coverage([_item("bachelor's degree", None, "", "qualification")], job)
    assert result.missing_required == [{"label": "sql (concept)", "checked_via": "taxonomy_concept"}]
    assert result.matched_preferred == [] and result.missing_preferred == []
    assert result.not_assessed_required == ["bachelor's degree"]
    assert result.not_assessed_preferred == ["3 years experience", "aws certified"]
    assert result.candidate_skill_count == 0


def test_ranking_is_lexicographic_without_weights() -> None:
    from types import SimpleNamespace
    from uuid import UUID

    from app.services.matching_service import coverage_ranking_key as ranking_key

    def match(job, matched_req, total_req, matched_pref=0, total_pref=0):
        return SimpleNamespace(
            job_id=UUID(int=job),
            matched_required=[{}] * matched_req, missing_required=["x"] * (total_req - matched_req),
            matched_preferred=[{}] * matched_pref, missing_preferred=["x"] * (total_pref - matched_pref),
        )

    jobs = {
        "no_required": (match(1, 0, 0, 3, 3), 0.99),
        "half_required": (match(2, 1, 2, 0, 1), 0.99),
        "full_no_preferred": (match(3, 2, 2), 0.99),
        "full_some_preferred": (match(4, 1, 1, 0, 4), None),
        "third_low_sim": (match(5, 1, 3, 1, 1), 0.10),
        "third_high_sim": (match(6, 2, 6, 1, 1), 0.90),   # 2/6 == 1/3 exactly
        "third_unindexed": (match(7, 1, 3, 1, 1), None),
    }
    order = sorted(jobs, key=lambda name: ranking_key(*jobs[name]))
    # Equal fractions: more matched skills first (2 of 6 before 1 of 3), then similarity.
    assert order == ["full_some_preferred", "full_no_preferred", "half_required",
                     "third_high_sim", "third_low_sim", "third_unindexed", "no_required"]


def test_ranking_prefers_more_matched_skills_when_fractions_tie() -> None:
    from types import SimpleNamespace
    from uuid import UUID

    from app.services.matching_service import coverage_ranking_key as ranking_key

    def match(job, matched_req, total_req, matched_pref=0, total_pref=0):
        return SimpleNamespace(
            job_id=UUID(int=job),
            matched_required=[{}] * matched_req, missing_required=[{}] * (total_req - matched_req),
            matched_preferred=[{}] * matched_pref, missing_preferred=[{}] * (total_pref - matched_pref),
        )

    jobs = {
        "one_of_one_high_sim": (match(1, 1, 1), 0.99),
        "two_of_two_low_sim": (match(2, 2, 2), 0.10),
        "two_of_two_more_preferred": (match(3, 2, 2, 2, 4), None),
        "two_of_two_fewer_preferred": (match(4, 2, 2, 1, 2), 0.99),
        "one_of_two_high_sim": (match(5, 1, 2), 0.99),
        "two_of_four_low_sim": (match(6, 2, 4), 0.10),
    }
    order = sorted(jobs, key=lambda name: ranking_key(*jobs[name]))
    assert order == ["two_of_two_more_preferred", "two_of_two_fewer_preferred",
                     "two_of_two_low_sim", "one_of_one_high_sim",
                     "two_of_four_low_sim", "one_of_two_high_sim"]


def test_missing_skill_schema_reads_legacy_bare_labels() -> None:
    from app.schemas.documents import MissingSkillRead

    # Older rows hold a bare label; only concept-checked skills were stored that way.
    assert MissingSkillRead.model_validate("git").model_dump() == {"label": "git", "checked_via": "taxonomy_concept", "reviewed": True, "esco_area": None}
    assert MissingSkillRead.model_validate({"label": "rust", "checked_via": "skill_name"}).checked_via == "skill_name"


def test_explanation_is_built_from_lists_without_cutoffs() -> None:
    from app.services.matching_service import CoverageResult, build_explanation

    empty = build_explanation(CoverageResult())
    assert empty.splitlines() == ["This job lists no comparable required skills.",
                                  "This job lists no comparable preferred skills."]
    text = build_explanation(CoverageResult(
        matched_required=[{"label": "python", "matched_via": "skill_name"}],
        missing_required=[{"label": "docker", "checked_via": "taxonomy_concept"},
                          {"label": "sql", "checked_via": "skill_name"}],
        missing_preferred=[{"label": "kubernetes", "checked_via": "skill_name"}]))
    lines = text.splitlines()
    assert lines[0] == "Required skills: 1 of 3 matched (python); missing: docker, sql."
    assert lines[1] == "Preferred skills: 0 of 1 matched; missing: kubernetes."
    assert lines[2] == "Checked by name only (may appear in your CV under a different wording): sql, kubernetes."
    assert len(lines) == 3
    for banned in ("%", "Strong", "Partial", "Limited", "Low match"):
        assert banned not in text


# ---- Job extraction contract v3 ------------------------------------------------------

JOB_POSTING = """Data Engineer
About the Role
You will build pipelines with Git.
Qualifications
3-5 years of relevant experience with Python.
Desirable
Docker
Bonus: Kubernetes
Benefits
Free AWS training and Agile coaching.
Equal Opportunity
We use SQL to track nothing.
How to Apply
Send a Linux screenshot."""


def _job_terms(text: str, extractor: SkillExtractor | None = None):
    return (extractor or SkillExtractor()).extract_from_sections(detect_job_segments(text), text, "job")


def test_job_requirement_types_follow_section_headings_and_skip_excluded_sections() -> None:
    terms = _job_terms(JOB_POSTING)
    by_name = {term.normalized_text: term for term in terms}
    assert by_name["git"].requirement_type == "unknown" and by_name["git"].source_section == "responsibilities"
    assert by_name["python"].requirement_type == "required"
    assert by_name["3-5 years of relevant experience"].requirement_type == "required"
    assert by_name["docker"].requirement_type == "preferred"
    assert by_name["kubernetes"].requirement_type == "preferred"  # inline "Bonus:" heading
    # Benefits, EEO and application text is not extracted at all.
    assert not {"aws", "agile", "sql", "linux"} & set(by_name)
    assert all(JOB_POSTING[term.start_char:term.end_char] == term.raw_text for term in terms)
    assert {term.extraction_method for term in terms} == {"dictionary@v3", "regex@v3"}


def test_job_segments_treat_text_without_headings_as_unknown_full_text() -> None:
    text = "We want Python and Docker skills."
    sections = detect_job_segments(text)
    assert [(s.section_type, s.content) for s in sections] == [("full_text", text)]
    assert {term.requirement_type for term in _job_terms(text)} == {"unknown"}


def test_excluded_headings_only_count_when_standing_alone() -> None:
    text = "Requirements\nSalary: competitive\nPython"
    terms = _job_terms(text)
    assert [(term.normalized_text, term.requirement_type) for term in terms] == [("python", "required")]


@pytest.mark.parametrize("heading", ["Attributes aligned with Core Values", "OUR VALUES", "Core Values:",
                                     "Our Culture", "Values & Behaviours"])
def test_company_values_headings_are_skipped(heading) -> None:
    text = f"Requirements\nPython\n{heading}\nCustomer Focus: delivers SQL and Docker value.\nPreferred skills\nGit"
    assert classify_job_heading(heading) == ("excluded", len(heading))
    assert [(t.normalized_text, t.requirement_type) for t in _job_terms(text)] == [("python", "required"), ("git", "preferred")]


@pytest.mark.parametrize("line", ["Skills and Attributes", "Key Competencies", "Values: integrity",
                                  "Values & Behaviour Framework (PDF, 2.7MB)"])
def test_values_exclusion_does_not_catch_requirement_or_inline_lines(line) -> None:
    assert classify_job_heading(line) is None


def test_shared_section_detector_is_unchanged_for_job_headings() -> None:
    # Stored job sections and CV sections still use the v2 heading rules.
    types = [section.section_type for section in SectionDetectionService().detect(JOB_POSTING)]
    assert "preferred_skills" not in types and types[-1] == "qualifications"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3-5 years of relevant experience", "3-5 years of relevant experience"),
        ("1 to 3 years of HR experience", "1 to 3 years of hr experience"),
        ("0\u20132 years of hands-on laboratory experience", "0\u20132 years of hands-on laboratory experience"),
        ("3+ years embedded firmware development experience", "3+ years embedded firmware development experience"),
        ("at least 1 year of\nhands-on experience", "1 year of hands-on experience"),
        ("5 years experience", "5 years experience"),
    ],
)
def test_job_experience_pattern_matches_ranges(text: str, expected: str) -> None:
    terms = [term for term in _job_terms(text) if term.term_type == "experience_indicator"]
    assert [term.normalized_text for term in terms] == [expected]


@pytest.mark.parametrize("text", ["5 years ago we shipped", "experience in 3 projects", "2 years of a long and varied career experience"])
def test_job_experience_pattern_rejects_non_requirements(text: str) -> None:
    assert not [term for term in _job_terms(text) if term.term_type == "experience_indicator"]


def test_cv_extraction_keeps_v2_experience_pattern() -> None:
    text = "3-5 years of relevant experience. 5 years experience."
    terms = SkillExtractor().extract_from_sections(SectionDetectionService().detect(text), text, "candidate")
    assert [term.normalized_text for term in terms if term.term_type == "experience_indicator"] == ["5 years experience"]


def _vocabulary() -> EscoVocabulary:
    concept = EscoConceptLabels
    return EscoVocabulary.from_concepts(
        [
            concept("skill", "cross-sector", True, ("Python (computer programming)", "Python")),
            concept("skill", "cross-sector", True, ("LESS",)),
            concept("skill", "cross-sector", True, ("R",)),
            concept("knowledge", "sector-specific", False, ("statistics", "statistical analysis")),
            concept("skill", "cross-sector", False, ("root cause analysis",)),
            concept("skill", "transversal", False, ("work independently",)),
            concept("skill", "transversal", False, ("communication",)),
            concept("knowledge", "cross-sector", True, ("database management systems", "database")),
        ],
        "ESCO-test",
    )


def test_esco_vocabulary_applies_filter_o7() -> None:
    vocabulary = _vocabulary()
    text = "Do root cause analysis and statistical analysis, work independently with communication, R and LESS."
    found = {label for _, _, label, _ in vocabulary.find(text)}
    # multi-word non-transversal and digital labels match; transversal, single-word non-digital and 1-char do not.
    assert found == {"root cause analysis", "statistical analysis", "less"}
    assert not vocabulary.find("we need less paperwork")  # ESCO spells it "LESS"
    assert [label for _, _, label, _ in vocabulary.find("python, database")] == ["database"]  # "Python" is cased
    assert {label: kind for _, _, label, kind in vocabulary.find("Python and database management systems")} == {
        "python": "skill", "database management systems": "domain_knowledge"}


def test_esco_terms_never_duplicate_dictionary_matches_and_record_version() -> None:
    text = "Requirements\nPython and database management systems.\nDo root cause analysis."
    terms = _job_terms(text, SkillExtractor(esco_vocabulary=_vocabulary()))
    by_name = {term.normalized_text: term for term in terms}
    assert by_name["python"].extraction_method == "dictionary@v3"  # curated dictionary wins on overlap
    esco = [term for term in terms if term.extraction_method.startswith("esco_vocabulary")]
    assert {term.normalized_text for term in esco} == {"database management systems", "root cause analysis"}
    assert {term.extraction_method for term in esco} == {"esco_vocabulary@v3:ESCO-test:o7"}
    assert all(term.requirement_type == "required" and text[term.start_char:term.end_char] == term.raw_text for term in esco)


def _seed_esco_release(db_session: Session, is_sample: bool = False) -> None:
    source = TaxonomySource(code="ESCO", name="ESCO")
    version = TaxonomyVersion(source=source, version="9.9", status="active", is_sample=is_sample,
                              imported_at=datetime.now(timezone.utc))
    db_session.add_all([source, version])
    db_session.flush()
    for index, (label, reuse, schemes, alternatives) in enumerate([
        ("root cause analysis", "cross-sector", "", ()),
        ("PostgreSQL", "cross-sector", ESCO_DIGITAL_SCHEME, ()),
        ("communication", "transversal", "", ("communicate",)),
    ]):
        concept = TaxonomyConcept(taxonomy_version_id=version.id, external_id=f"esco:test:{index}", preferred_label=label,
                                  normalized_label=label.lower(), concept_type="skill",
                                  metadata_json={"source": {"reuseLevel": reuse, "inScheme": schemes}})
        concept.labels = [TaxonomyLabel(label=alt, normalized_label=alt, label_type="alternative") for alt in alternatives]
        db_session.add(concept)
    db_session.commit()


@pytest.mark.usefixtures("v3_jobs")
def test_esco_vocabulary_config_switch_compares_old_and_new(client: TestClient, db_session: Session, monkeypatch) -> None:
    _seed_esco_release(db_session)
    assert build_job_extractor(db_session, use_esco_vocabulary=False).esco_vocabulary is None
    assert build_job_extractor(db_session, use_esco_vocabulary=True).esco_vocabulary.version == "ESCO-9.9"
    headers = job_manager_headers(client, db_session)
    description = "Requirements\nRoot cause analysis and communication."

    def process(enabled: bool) -> set[tuple[str, str]]:
        monkeypatch.setattr(settings, "JOB_EXTRACTION_ESCO_VOCABULARY", enabled)
        job = client.post("/jobs", headers=headers, json={
            "title": f"Ops {enabled}", "company": "Example", "location": "Remote",
            "employment_type": "Full-time", "description": description})
        assert job.status_code == 201
        rows = db_session.scalars(select(JobSkill).where(JobSkill.job_id == UUID(job.json()["id"])))
        return {(row.normalized_text, row.requirement_type) for row in rows}

    assert process(False) == set()
    assert process(True) == {("root cause analysis", "required")}  # transversal "communication" filtered out


def test_sample_esco_releases_are_never_used_as_vocabulary(db_session: Session) -> None:
    _seed_esco_release(db_session, is_sample=True)
    assert build_job_extractor(db_session, use_esco_vocabulary=True).esco_vocabulary is None


# ---- Additive re-extraction ------------------------------------------------------------

def _legacy_job(client: TestClient, db_session: Session, description: str):
    """Create a job, then make its stored extraction look like contract v2."""
    from app.db.models import Job
    from app.services.section_detection_service import SectionDetectionService as V2Sections

    headers = job_manager_headers(client, db_session)
    response = client.post("/jobs", headers=headers, json={
        "title": "Legacy", "company": "Example", "location": "Remote", "employment_type": "Full-time",
        "description": description})
    assert response.status_code == 201
    job = db_session.get(Job, UUID(response.json()["id"]))
    from dataclasses import replace

    # v2 job extraction = v2 patterns and sections; requirement only from required/preferred skills headings.
    v2_requirements = {"required_skills": "required", "preferred_skills": "preferred"}
    v2_terms = [
        replace(term, requirement_type=v2_requirements.get(term.source_section, "unknown"))
        for term in SkillExtractor().extract_from_sections(
            V2Sections().detect(job.cleaned_description), job.cleaned_description, "candidate")
    ]
    assert all(term.extraction_method.endswith("@v2") for term in v2_terms)
    from app.repositories.document_repository import DocumentRepository
    DocumentRepository(db_session).replace_job_terms(job, v2_terms)
    db_session.commit()
    return job, headers


@pytest.mark.usefixtures("v3_jobs")
def test_additive_reextraction_keeps_reviews_and_adds_new_terms_as_pending(
    client: TestClient, db_session: Session
) -> None:
    from app.db.models import ProcessingLog
    from app.services.job_service import JobReextractionService

    description = "Qualifications\nPython, Docker and Git\n3-5 years of relevant experience\nBenefits\nAWS credits"
    job, _ = _legacy_job(client, db_session, description)
    skills = {s.normalized_text: s for s in db_session.scalars(select(JobSkill).where(JobSkill.job_id == job.id))}
    assert {"python", "docker", "git", "aws"} <= set(skills)
    skills["python"].review_status = "approved"
    skills["docker"].review_status = "rejected"
    db_session.commit()
    before = {s.id: (s.review_status, s.requirement_type) for s in skills.values()}

    service = JobReextractionService(db_session, use_esco_vocabulary=False)
    plan = service.plan(job)
    assert [t.normalized_text for t in plan.new_terms] == ["3-5 years of relevant experience"]
    assert [(s.normalized_text, new) for _, s, new in plan.pending_type_changes] == [("git", "required")]
    # Approved unknown -> required is applied (review kept); a rejected skill is only reported.
    assert [(s.normalized_text, new) for _, s, new in plan.approved_upgrades] == [("python", "required")]
    assert [(s.normalized_text, new) for _, s, new in plan.reviewed_type_changes] == [("docker", "required")]
    assert [term.normalized_text for term, _ in plan.vanished] == ["aws"]  # now under Benefits
    db_session.rollback()  # planning writes nothing
    assert {s.id: (s.review_status, s.requirement_type) for s in
            db_session.scalars(select(JobSkill).where(JobSkill.job_id == job.id))} == before

    service.apply(job, service.plan(job))
    after = {s.normalized_text: s for s in db_session.scalars(select(JobSkill).where(JobSkill.job_id == job.id))}
    assert (after["python"].review_status, after["python"].requirement_type) == ("approved", "required")
    assert (after["docker"].review_status, after["docker"].requirement_type) == ("rejected", "unknown")
    assert (after["git"].review_status, after["git"].requirement_type) == ("pending", "required")
    assert after["aws"].id == skills["aws"].id  # vanished occurrence kept
    new = after["3-5 years of relevant experience"]
    assert (new.review_status, new.requirement_type, new.source) == ("pending", "required", "extraction")
    assert db_session.scalar(select(ExtractedJobTerm.extraction_method).where(ExtractedJobTerm.id == new.extracted_term_id)) == "regex@v3"
    logs = db_session.scalars(select(ProcessingLog).where(ProcessingLog.stage == "additive_reextraction",
                                                         ProcessingLog.entity_id == job.id))
    assert any(log.metadata_json["new_terms"] == 1 and log.metadata_json["approved_unknown_upgrades"] == 1
               for log in logs)

    # Idempotent: a second run finds nothing new and changes nothing.
    second = service.plan(job)
    assert not second.changes_data and second.new_terms == []


def test_additive_reextraction_links_only_new_terms(client: TestClient, db_session: Session, monkeypatch) -> None:
    from app.services import job_service

    job, _ = _legacy_job(client, db_session, "Requirements\nPython\n2-4 years of industry experience")
    linked: list[set] = []
    monkeypatch.setattr(job_service.TaxonomyService, "link_document_if_taxonomy_available",
                        lambda self, source, document_id, term_ids=None: linked.append(term_ids))
    service = job_service.JobReextractionService(db_session, use_esco_vocabulary=False)
    new_ids = service.apply(job, service.plan(job))
    assert len(new_ids) == 1 and linked == [set(new_ids)]


@pytest.mark.usefixtures("v3_jobs")
def test_reextraction_cli_dry_run_writes_nothing(client: TestClient, db_session: Session, monkeypatch, capsys) -> None:
    from app.services import job_service

    job, _ = _legacy_job(client, db_session, "Requirements\nPython\n2-4 years of industry experience")
    job_id = job.id
    count = lambda: len(list(db_session.scalars(select(ExtractedJobTerm).where(ExtractedJobTerm.job_id == job_id))))
    before = count()
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db_session)
    assert job_service.main(["reextract", "--esco", "off", "--sources", "all", "--job", str(job_id)]) == 0
    output = capsys.readouterr().out
    assert "DRY-RUN (no writes)" in output and "new   1" in output
    assert count() == before


@pytest.mark.usefixtures("v3_jobs")
def test_reextraction_does_not_re_add_text_a_reviewer_corrected(client: TestClient, db_session: Session) -> None:
    from app.services.job_service import JobReextractionService

    job, headers = _legacy_job(client, db_session, "Requirements\nNABCEP certification")
    skill = db_session.scalar(select(JobSkill).where(JobSkill.job_id == job.id, JobSkill.normalized_text == "certification"))
    payload = {"raw_text": "certification", "normalized_text": "nabcep certification", "skill_type": "certification",
               "requirement_type": "required", "evidence_sentence": skill.evidence_sentence, "review_status": "approved"}
    assert client.put(f"/jobs/{job.id}/extracted-skills/{skill.id}", headers=headers, json=payload).status_code == 200
    db_session.expire_all()

    plan = JobReextractionService(db_session, use_esco_vocabulary=False).plan(job)
    assert plan.new_terms == [] and plan.vanished == []
    [(stored_term, kept_skill, fresh)] = plan.reviewer_edited
    assert (kept_skill.normalized_text, kept_skill.review_status, fresh.normalized_text) == (
        "nabcep certification", "approved", "certification")


# ---- Job create/edit uses the same additive reconciliation -----------------------------

def _create_job(client: TestClient, headers: dict, description: str) -> dict:
    response = client.post("/jobs", headers=headers, json={
        "title": "Edited", "company": "Example", "location": "Remote", "employment_type": "Full-time",
        "description": description})
    assert response.status_code == 201
    return response.json()


def _edit_job(client: TestClient, headers: dict, job_id: str, description: str) -> None:
    response = client.put(f"/jobs/{job_id}", headers=headers, json={
        "title": "Edited", "company": "Example", "location": "Remote", "employment_type": "Full-time",
        "description": description, "status": "processed"})
    assert response.status_code == 200


def _skills(client: TestClient, headers: dict, job_id: str) -> list[dict]:
    return client.get(f"/jobs/{job_id}/extracted-skills", headers=headers).json()


def test_job_edit_keeps_reviews_and_does_not_duplicate_skills(client: TestClient, db_session: Session) -> None:
    from app.db.models import Job

    headers = job_manager_headers(client, db_session)
    job = _create_job(client, headers, "Requirements\nPython\nDocker")
    python = next(s for s in _skills(client, headers, job["id"]) if s["normalized_text"] == "python")
    python.update(review_status="approved")
    assert client.put(f"/jobs/{job['id']}/extracted-skills/{python['id']}", headers=headers, json=python).status_code == 200

    _edit_job(client, headers, job["id"], "Requirements\nPython\nDocker")  # unchanged text
    assert sorted(s["normalized_text"] for s in _skills(client, headers, job["id"])) == ["docker", "python"]

    # Prepending text shifts every offset; the reviewed occurrence moves instead of being duplicated.
    _edit_job(client, headers, job["id"], "About the job\nWe build tools with Git.\nRequirements\nPython\nDocker")
    skills = _skills(client, headers, job["id"])
    assert sorted(s["normalized_text"] for s in skills) == ["docker", "git", "python"]
    kept = next(s for s in skills if s["normalized_text"] == "python")
    assert (kept["id"], kept["review_status"]) == (python["id"], "approved")
    assert next(s for s in skills if s["normalized_text"] == "git")["review_status"] == "pending"
    db_session.expire_all()
    stored = db_session.get(Job, UUID(job["id"]))
    term = db_session.scalar(select(ExtractedJobTerm).where(ExtractedJobTerm.id == db_session.get(JobSkill, UUID(kept["id"])).extracted_term_id))
    assert stored.cleaned_description[term.start_char:term.end_char] == "Python"


def test_job_edit_keeps_evidence_for_removed_text_and_adds_new_terms_as_pending(
    client: TestClient, db_session: Session
) -> None:
    headers = job_manager_headers(client, db_session)
    job = _create_job(client, headers, "Requirements\nPython\nDocker")
    _edit_job(client, headers, job["id"], "Requirements\nPython\nKubernetes")
    by_name = {s["normalized_text"]: s for s in _skills(client, headers, job["id"])}
    assert set(by_name) == {"python", "docker", "kubernetes"}  # removed Docker evidence kept for review
    assert by_name["kubernetes"]["review_status"] == "pending"
    assert by_name["kubernetes"]["requirement_type"] == "required"
