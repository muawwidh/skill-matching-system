import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Role, User
from app.nlp.skill_extractor import SkillExtractor
from app.services.document_parser_service import DocumentParserService
from app.services.pdf_text_normalization_service import PdfTextNormalizationService
from app.services.section_detection_service import SectionDetectionService
from app.services.text_cleaning_service import TextCleaningService


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "candidate@example.com",
            "full_name": "Candidate Example",
            "password": "correct-horse-password",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_text_cleaning_collapses_extra_spacing() -> None:
    cleaned = TextCleaningService().clean(" Python\t\tFastAPI\n\n\n\nSQL ")
    assert cleaned == "Python FastAPI\n\nSQL"


def test_section_detection_finds_cv_sections() -> None:
    text = "Summary\nBackend engineer\n\nSkills\nPython\nSQL\n\nEducation\nMSc"
    sections = SectionDetectionService().detect(text)
    assert [section.section_type for section in sections] == ["summary", "skills", "education"]
    assert sections[1].content == "Python\nSQL"


def test_section_detection_handles_pdf_style_heading_variants() -> None:
    text = (
        "PROFESSIONAL SUMMARY:\nBackend engineer\n\n"
        "PROFESSIONAL EXPERIENCE\nBuilt APIs\n\n"
        "KEY SKILLS:\nPython\nSQL\n\n"
        "ACADEMIC QUALIFICATIONS\nMSc Computer Science"
    )
    sections = SectionDetectionService().detect(text)
    assert [section.section_type for section in sections] == [
        "summary",
        "work_experience",
        "skills",
        "education",
    ]


@pytest.mark.parametrize(
    ("source", "normalized_expected", "section_types", "expected_terms"),
    [
        (
            "Developer with 5 years of experience in Python and SQL.",
            "Developer with 5 years of experience in Python and SQL.",
            ["full_text"], {"5 years of experience", "python", "sql"},
        ),
        (
            "Jane Doe Professional Summary Backend developer…",
            "Jane Doe Professional Summary Backend developer…",
            ["full_text"], set(),
        ),
        (
            "Professional Summary\nBackend developer with Python.",
            "Professional Summary\nBackend developer with Python.",
            ["summary"], {"python"},
        ),
        (
            "Education and certifications\nMSc Computer Science",
            "Education and certifications\nMSc Computer Science",
            ["education"], {"msc"},
        ),
        ("Skills: Python, SQL", "Skills: Python, SQL", ["skills"], {"python", "sql"}),
        (
            "Intro\nWork Experience\nBuilt APIs with Python.",
            "Intro\nWork Experience\nBuilt APIs with Python.",
            ["full_text", "work_experience"], {"python"},
        ),
        (
            "Led data projects; improved customer profile matching.",
            "Led data projects; improved customer profile matching.",
            ["full_text"], set(),
        ),
        ("Gained skills in Docker.", "Gained skills in Docker.", ["full_text"], {"docker"}),
        (
            "PROFILE Backend developer. EXPERIENCE 5 years experience with Python. SKILLS Docker, SQL.",
            "PROFILE\nBackend developer.\nEXPERIENCE\n5 years experience with Python.\nSKILLS\nDocker, SQL.",
            ["summary", "work_experience", "skills"],
            {"5 years experience", "python", "docker", "sql"},
        ),
        (
            "EXPERIENCE in Python and SKILLS acquired over time.",
            "EXPERIENCE in Python and SKILLS acquired over time.",
            ["full_text"], {"python"},
        ),
        (
            "PROFILE Backend developer. SKILLS Python, SQL.",
            "PROFILE\nBackend developer.\nSKILLS\nPython, SQL.",
            ["summary", "skills"], {"python", "sql"},
        ),
    ],
)
def test_pdf_normalization_golden_sections_and_extraction(
    source: str, normalized_expected: str, section_types: list[str], expected_terms: set[str]
) -> None:
    normalizer = PdfTextNormalizationService()
    normalized = normalizer.normalize(source)
    assert normalized == normalized_expected
    assert normalizer.normalize(source) == normalized
    sections = SectionDetectionService().detect(normalized)
    assert [section.section_type for section in sections] == section_types
    assert all(normalized[section.start_char : section.end_char] == section.content for section in sections)
    if source.startswith("Intro\nWork Experience"):
        assert sections[0].content == "Intro\n"
        assert sections[1].heading == "Work Experience"
    terms = SkillExtractor().extract_from_sections(sections, normalized, "candidate")
    assert {term.normalized_text for term in terms} >= expected_terms
    assert all(normalized[term.start_char : term.end_char] == term.raw_text for term in terms)


def test_flattened_uppercase_multiword_headings_keep_complete_section_boundaries() -> None:
    source = (
        "WORK EXPERIENCE Built Python APIs. PROFESSIONAL SUMMARY Backend engineer. "
        "TECHNICAL SKILLS Python, SQL."
    )
    expected = (
        "WORK EXPERIENCE\nBuilt Python APIs.\nPROFESSIONAL SUMMARY\nBackend engineer.\n"
        "TECHNICAL SKILLS\nPython, SQL."
    )
    normalizer = PdfTextNormalizationService()
    normalized = normalizer.normalize(source)
    assert normalized == expected
    assert normalizer.normalize(source) == normalized
    assert normalizer.normalize(normalized) == normalized

    sections = SectionDetectionService().detect(normalized)
    assert [(section.section_type, section.heading, section.content) for section in sections] == [
        ("work_experience", "WORK EXPERIENCE", "Built Python APIs."),
        ("summary", "PROFESSIONAL SUMMARY", "Backend engineer."),
        ("skills", "TECHNICAL SKILLS", "Python, SQL."),
    ]
    assert all(normalized[section.start_char : section.end_char] == section.content for section in sections)
    assert all(first.end_char <= second.start_char for first, second in zip(sections, sections[1:]))
    assert all(word not in section.content for section in sections for word in ("WORK", "PROFESSIONAL", "TECHNICAL"))
    terms = SkillExtractor().extract_from_sections(sections, normalized, "candidate")
    assert {"python", "sql"} <= {term.normalized_text for term in terms}
    assert all(normalized[term.start_char : term.end_char] == term.raw_text for term in terms)


def test_section_detection_preserves_exact_preamble_and_nonoverlapping_offsets() -> None:
    text = "5 years experience with Python.\nProfessional Summary\nBackend developer.\nSkills\nSQL"
    sections = SectionDetectionService().detect(text)
    assert [section.section_type for section in sections] == ["full_text", "summary", "skills"]
    assert sections[0].content == text[: text.index("Professional Summary")]
    assert (sections[0].start_char, sections[0].end_char) == (0, text.index("Professional Summary"))
    assert all(text[section.start_char : section.end_char] == section.content for section in sections)
    assert all(first.end_char <= second.start_char for first, second in zip(sections, sections[1:]))
    without_headings = text
    for start, end, _, _ in reversed(SectionDetectionService()._find_headings(text)):
        without_headings = without_headings[:start] + " " + without_headings[end:]
    assert without_headings.split() == " ".join(section.content for section in sections).split()
    terms = SkillExtractor().extract_from_sections(sections, text, "candidate")
    assert {term.normalized_text for term in terms} >= {"5 years experience", "python", "sql"}
    assert {term.source_section for term in terms if term.normalized_text == "python"} == {"full_text"}


def test_whitespace_only_preamble_does_not_create_a_section() -> None:
    text = " \n\nSkills: Python"
    sections = SectionDetectionService().detect(text)
    assert [section.section_type for section in sections] == ["skills"]
    assert text[sections[0].start_char : sections[0].end_char] == "Python"


def test_txt_parser_validates_supported_content() -> None:
    parser = DocumentParserService()
    parsed = parser.parse_upload("cv.txt", "text/plain", b"Skills\nPython")
    assert parsed.text == "Skills\nPython"


def test_candidate_can_paste_cv_and_view_sections(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Summary\nBackend engineer\n\nSkills\nPython\nFastAPI\n\nProjects\nAPI platform",
            "original_filename": "manual-cv.txt",
            "consent_to_process": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processed"
    assert {section["section_type"] for section in body["sections"]} >= {"summary", "skills"}

    list_response = client.get("/cvs", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_cv_processing_requires_consent(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "Skills\nPython",
            "original_filename": "manual-cv.txt",
            "consent_to_process": False,
        },
    )
    assert response.status_code == 400


def test_candidate_can_upload_txt_cv(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/cvs/upload",
        headers=headers,
        data={"consent_to_process": "true"},
        files={"file": ("cv.txt", b"Skills\nPython\nSQL", "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["content_type"] == "text/plain"


def test_job_creation_processes_sections(client: TestClient, db_session: Session) -> None:
    candidate_headers = auth_headers(client)
    registration = client.post(
        "/auth/register",
        json={
            "email": "job-admin@example.com",
            "full_name": "Synthetic Job Administrator",
            "password": "correct-horse-password",
        },
    )
    assert registration.status_code == 201
    user = db_session.scalar(select(User).where(User.email == "job-admin@example.com"))
    assert user is not None
    user.roles.append(Role(name="admin", description="Job administration"))
    db_session.commit()
    admin_headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    response = client.post(
        "/jobs",
        headers=admin_headers,
        json={
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "employment_type": "Full-time",
            "description": "Responsibilities\nBuild APIs\n\nRequired skills\nPython\nSQL",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processed"
    assert {section["section_type"] for section in body["sections"]} >= {
        "responsibilities",
        "required_skills",
    }

    assert client.get("/jobs", headers=candidate_headers).status_code == 200
    logs_response = client.get("/admin/logs", headers=candidate_headers)
    assert logs_response.status_code == 403
