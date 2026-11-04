import hashlib
import os

import pytest

from app.retrieval.embedder import load_local_tokenizer
from app.retrieval.representation import (TEMPLATE_V1, TEMPLATE_V2, build_job_representation,
    candidate_representation_v1, candidate_representation_v2, job_representation_v1, job_representation_v2)
from conftest import DeterministicTestTokenizer


def job():
    return dict(title="Engineer", company="Example", location="City", employment_type="full-time",
                description="Original source", status="processed")


def terms():
    return [dict(id="b", text="Python", normalized="python", type="skill", status="pending", requirement="required",
                 canonical="Python programming", release="active", term_id="t1"),
            dict(id="a", text="SQL", normalized="sql", type="skill", status="approved", requirement="preferred",
                 canonical="", release="", term_id="t2"),
            dict(id="c", text="Git", normalized="git", type="tool", status="pending", requirement="unknown",
                 canonical="", release="", term_id="t3"),
            dict(id="d", text="RejectedOnly", normalized="rejectedonly", type="skill", status="rejected", requirement="required",
                 canonical="", release="", term_id="t4")]


def sections(reverse=False):
    bodies = [("responsibilities", "Develop systems and maintain services. " * 100),
              ("required_skills", "RequiredMarker experience building reliable software. " * 100)]
    if reverse:
        bodies.reverse()
    return [dict(section_type=kind, content=body, start_char=i * 10000, end_char=(i+1) * 10000)
            for i, (kind, body) in enumerate(bodies)]


def test_v1_byte_for_byte_baseline_and_candidate_v2_semantics():
    original = job_representation_v1(job(), terms())
    expected = ("passage: Job title: Engineer\nEmployment: full-time\nLocation: City\n"
                "Required skills: Python; Python programming\nPreferred skills: SQL\nOther skills: Git\nDescription: Original source")
    assert original.text == expected
    assert hashlib.sha256(original.text.encode()).hexdigest() == hashlib.sha256(expected.encode()).hexdigest()
    assert build_job_representation(job(), terms(), sections(), TEMPLATE_V1).text == expected
    rows = [dict(id="2", text="Pending", status="pending", evidence="Do not include"),
            dict(id="1", text="Python", status="approved", evidence="Built an API", canonical="Python programming", release="v")]
    v1, v2 = candidate_representation_v1(rows), candidate_representation_v2(rows)
    assert v1.text == v2.text == "query: Skills: Python; Python programming\nEvidence: Built an API"
    assert v1.source_hash != v2.source_hash
    assert candidate_representation_v2(list(reversed(rows))) == v2
    assert candidate_representation_v2(rows[:1]) is None


@pytest.mark.parametrize("reverse", [False, True])
def test_v2_reserves_requirements_and_responsibilities_in_either_source_order(reverse):
    value = job_representation_v2(job(), [], sections(reverse), DeterministicTestTokenizer())
    assert "RequiredMarker" in value.text and "Develop systems" in value.text
    assert "Source requirements:" in value.text and "Source responsibilities:" in value.text
    assert value.details["substantive_classes_lost"] == []
    assert value.details["tokens"] <= 512


def test_zero_terms_full_text_heading_and_line_cue_fallbacks():
    tokenizer = DeterministicTestTokenizer()
    for description, fallback in [
        ("Requirements\nRequiredMarker proficiency.\nResponsibilities\nDevelop systems.", "stored/headings"),
        ("Experience with systems is needed.\nDevelop systems safely.", "line-cues+stratified-context"),
        ("Unclassified source wording.\nAnother source line.\nFinal original source line.", "stratified-context"),
    ]:
        value = job_representation_v2({**job(), "description": description}, [], [], tokenizer)
        assert value.details["fallback"] == fallback
        assert value.details["selected"]
        assert value.details["tokens"] <= 512
        if "Requirements" in description:
            assert "RequiredMarker" in value.text and "Develop systems" in value.text


def test_duplicate_sections_lines_order_hash_sensitivity_and_structured_priority():
    tokenizer = DeterministicTestTokenizer()
    base = [dict(section_type="responsibilities", content="Develop services.\nDevelop services.", start_char=1)]
    value = job_representation_v2(job(), terms(), base + base, tokenizer)
    assert value.text.count("Develop services.") == 1
    assert value.details["duplicate_lines"] == 3
    assert value.text.index("Required skills:") < value.text.index("Preferred skills:") < value.text.index("Other skills:")
    assert "RejectedOnly" not in value.text
    assert value == job_representation_v2(job(), list(reversed(terms())), base + base, tokenizer)
    assert value == job_representation_v2(job(), terms(), base + base, tokenizer)
    changed = job_representation_v2({**job(), "description": "Changed complete source"}, terms(), base + base, tokenizer)
    assert value.source_hash != changed.source_hash
    assert value.source_hash != job_representation_v1(job(), terms()).source_hash
    changed_section = [{**base[0], "content": base[0]["content"] + "\nUnselected source change."}]
    assert job_representation_v2(job(), terms(), changed_section, tokenizer).source_hash != value.source_hash


def test_unicode_technical_names_and_metadata_overflow_are_valid_and_bounded():
    tokenizer = DeterministicTestTokenizer()
    source = [dict(section_type="required_skills", content="Knowledge of C++ C# .NET Node.js and Python.\nUnicode: Žinių 東京", start_char=0)]
    value = job_representation_v2(job(), [], source, tokenizer)
    assert all(name in value.text for name in ("C++", "C#", ".NET", "Node.js"))
    assert "東京" in value.text
    value.text.encode("utf-8", errors="strict")
    huge = {**job(), "title": "Long technical title " * 100, "location": "Location " * 100,
            "employment_type": "Employment " * 100}
    bounded = job_representation_v2(huge, terms(), sections(), tokenizer)
    assert bounded.details["tokens"] <= 512
    assert all(label in bounded.text for label in ("passage: Job title:", "Employment:", "Location:"))
    assert not bounded.details["substantive_classes_lost"]
    with pytest.raises(ValueError, match="Unsupported"):
        build_job_representation(job(), [], [], "unsupported", tokenizer)
    with pytest.raises(RuntimeError, match="tokenizer"):
        build_job_representation(job(), [], [], TEMPLATE_V2)


def test_pinned_offline_tokenizer_v2_budget_and_determinism():
    path = os.environ.get("PHASE5_REAL_MODEL_PATH")
    if not path:
        pytest.skip("UNVERIFIED: pinned local tokenizer path is not configured")
    tokenizer = load_local_tokenizer(path)
    for reverse in (False, True):
        source = sections(reverse) + [dict(section_type="preferred_skills", content="C++ .NET Node.js SQL " * 100, start_char=30000)]
        value = job_representation_v2(job(), terms(), source, tokenizer)
        assert len(tokenizer.encode(value.text, add_special_tokens=True)) <= 512
        assert value == job_representation_v2(job(), terms(), source, tokenizer)
        assert "RequiredMarker" in value.text and "Develop systems" in value.text
        assert not value.details["substantive_classes_lost"]


def test_v2_repository_excludes_inactive_and_stale_canonicals(db_session):
    from sqlalchemy import select
    from app.db.models import ExtractedJobTerm, JobSkill
    from app.repositories.retrieval_repository import RetrievalRepository
    from app.repositories.taxonomy_repository import TaxonomyRepository
    from test_retrieval import seed
    db = db_session
    _, _, _, _, _, owner = seed(db)
    skill = db.scalar(select(JobSkill).where(JobSkill.job_id == owner.id))
    term = ExtractedJobTerm(job_id=owner.id, raw_text=skill.raw_text, normalized_text=skill.normalized_text,
                            term_type=skill.skill_type, extraction_method="test")
    db.add(term)
    db.flush()
    skill.extracted_term_id = term.id
    taxonomy = TaxonomyRepository(db)
    source = taxonomy.get_or_create_source("TEST", "Test", "", "")
    version = taxonomy.replace_version(source, "test", "", "test", "", True)
    concept = taxonomy.add_concept(version.id, "x", "CanonicalIdentity", "canonicalidentity", "", "skill", "en", [], {})
    candidate = taxonomy.add_link_candidate("job", term.id, term.raw_text, term.normalized_text,
                                           concept.id, "exact", 1.0, 1, "approved")
    taxonomy.approve_candidate(candidate, "automatic", None)
    db.commit()
    repo = RetrievalRepository(db, TEMPLATE_V2, DeterministicTestTokenizer())
    assert "CanonicalIdentity" in repo.job_input(owner).text
    version.status = "inactive"
    db.flush()
    assert "CanonicalIdentity" not in repo.job_input(owner).text
    version.status = "active"
    term.raw_text = "Different extraction"
    db.flush()
    assert "CanonicalIdentity" not in repo.job_input(owner).text


def test_short_lines_fill_reserved_budget_and_cues_refine_broad_sections():
    tokenizer = DeterministicTestTokenizer()
    source = [{"section_type": "summary", "start_char": 0,
        "content": "\n".join([f"Develop service {i} safely." for i in range(40)] +
                              [f"Experience with technology {i} is required." for i in range(40)])}]
    value = job_representation_v2(job(), [], source, tokenizer)
    assert 350 <= value.details["tokens"] <= 512
    assert value.details["selected"]["requirements"] and value.details["selected"]["responsibilities"]
    assert not value.details["substantive_classes_lost"]


def test_duplicate_section_identity_order_is_deterministic_and_generic_headings_work():
    source = [dict(id=identity, section_type="full_text", start_char=0,
                   content="Key job responsibilities\nDevelop services.\nMinimum technical skills\nExperience with systems.")
              for identity in ("b", "a")]
    tok = DeterministicTestTokenizer()
    first = job_representation_v2(job(), [], source, tok)
    second = job_representation_v2(job(), [], list(reversed(source)), tok)
    assert first.text == second.text and first.source_hash == second.source_hash
    assert first.details["selected"]["requirements"] and first.details["selected"]["responsibilities"]
    with pytest.raises(RuntimeError, match="unavailable"):
        load_local_tokenizer("/definitely-missing-pinned-tokenizer")


def test_cli_selects_explicit_v1_and_v2_without_indexing(monkeypatch):
    from app.retrieval import cli
    calls = []
    monkeypatch.setattr(cli, "index", lambda *args: calls.append(args))
    for template in (TEMPLATE_V1, TEMPLATE_V2):
        monkeypatch.setattr("sys.argv", ["retrieval", "index", "jobs", "--limit", "3", "--template", template])
        cli.main()
        assert calls[-1] == ("jobs", 3, None, template)


def test_unheaded_candidate_conditions_and_role_statements_are_not_lost():
    source = [{"section_type": "full_text", "start_char": 0,
        "content": "Excellent interpersonal skills are essential.\nYou are able to organise work.\n"
                   "In this role you will coordinate services.\nThe remaining original context."}]
    value = job_representation_v2(job(), [], source, DeterministicTestTokenizer())
    assert value.details["selected"]["requirements"] and value.details["selected"]["responsibilities"]
    assert "Excellent interpersonal skills" in value.text


def test_unheaded_prior_experience_and_wrapped_adjectival_conditions():
    source = [{"section_type": "full_text", "start_char": 0,
        "content": "Prior experience working in a service organisation.\n"
                   "Excellent organisational and planning\nskills are expected.\n"
                   "Work with colleagues to deliver services."}]
    value = job_representation_v2(job(), [], source, DeterministicTestTokenizer())
    assert "Prior experience working in" in value.text and "Excellent organisational" in value.text
    assert value.details["selected"]["requirements"] and value.details["selected"]["responsibilities"]


def test_unheaded_preference_condition_does_not_become_required():
    source = [{"section_type": "required_skills", "start_char": 0,
               "content": "Experience with systems is preferred.\nKnowledge of operations is required."}]
    value = job_representation_v2(job(), [], source, DeterministicTestTokenizer())
    assert value.details["selected"]["requirements"] and value.details["selected"]["preferences"]
    assert "Source preferences: Experience with systems is preferred." in value.text


def test_single_line_fallback_is_stratified_and_sentence_cues_are_independent():
    text = " ".join([f"word{i}" for i in range(320)])
    value = job_representation_v2({**job(), "description": text}, [], [], DeterministicTestTokenizer())
    assert "word0" in value.text and "word256" in value.text
    mixed = "Develop services safely. Experience with systems is required."
    value = job_representation_v2({**job(), "description": mixed}, [], [], DeterministicTestTokenizer())
    assert value.details["selected"]["requirements"] and value.details["selected"]["responsibilities"]


@pytest.mark.parametrize("heading", ["Desired Skills", "desired skills:", "DESIRED SKILLS?",
                                     "Desired Qualifications", "desired qualifications:", "DESIRED QUALIFICATIONS?"])
def test_desired_section_aliases_are_preferred(heading):
    from app.retrieval.job_budget import _units
    buckets, _ = _units(job(), [{"section_type": "full_text", "content": heading +
                                "\nExperience with systems is useful.", "start_char": 0}], set())
    assert [r["text"] for r in buckets["preferences"]] == ["Experience with systems is useful."]
    assert not buckets["requirements"]


@pytest.mark.parametrize("line", [
    "Three years of support experience (software/IT preferred).",
    "Three years of support experience, with software/IT preferred.",
    "Three years of support experience with software/IT preferred.",
    "Support experience is required, while software experience is preferred.",
])
def test_parenthetical_or_subordinate_preference_keeps_required_line(line):
    from app.retrieval.job_budget import _units
    buckets, _ = _units(job(), [{"section_type": "required_skills", "content": line, "start_char": 0}], set())
    assert [r["text"] for r in buckets["requirements"]] == [line]
    assert not buckets["preferences"]


def test_subordinate_while_guard_preserves_required_line():
    from app.retrieval.job_budget import _units, _whole_line_preferred
    line = "Experience with Linux, while experience with Windows is preferred."
    # The optional tail is a valid predicate; only the subordinate-clause guard rejects the mixed line.
    assert _whole_line_preferred("Experience with Windows is preferred.") is True
    assert _whole_line_preferred(line) is False
    buckets, _ = _units(job(), [{"section_type": "full_text", "start_char": 0,
                                "content": "Requirements\n" + line}], set())
    assert [unit["text"] for unit in buckets["requirements"]] == [line]
    assert not buckets["preferences"]


@pytest.mark.parametrize("line", ["Experience with systems is preferred.",
                                 "Experience with systems would be an advantage.",
                                 "Preferred: experience with systems."])
def test_clear_whole_line_preference_can_override_required_heading(line):
    from app.retrieval.job_budget import _units
    buckets, _ = _units(job(), [{"section_type": "required_skills", "content": line, "start_char": 0}], set())
    assert [r["text"] for r in buckets["preferences"]] == [line]
    assert not buckets["requirements"]


def _pinned_tokenizer():
    path = os.environ.get("PHASE5_REAL_MODEL_PATH")
    if not path:
        pytest.skip("UNVERIFIED: pinned local tokenizer path is not configured")
    return load_local_tokenizer(path)


def test_pinned_tokenizer_oversized_first_draft_is_shrunk(monkeypatch):
    from app.retrieval import job_budget
    tokenizer = _pinned_tokenizer()
    original = job_budget._render_bucket
    injected = False

    def oversized_first_draft(kind, units, budget, tok):
        nonlocal injected
        text, trace = original(kind, units, budget, tok)
        if not injected:
            injected = True
            text += " data" * 64
        return text, trace

    monkeypatch.setattr(job_budget, "_render_bucket", oversized_first_draft)
    source = [{"section_type": kind, "start_char": index * 10000,
               "content": "\n".join(f"{prefix} {i} with reliable systems and clear documentation." for i in range(100))}
              for index, (kind, prefix) in enumerate((("required_skills", "Experience with technology"),
                                                     ("responsibilities", "Develop service")))]
    value = job_representation_v2(job(), [], source, tokenizer)
    assert value.details["initial_tokens"] > 512
    assert value.details["shrink_passes"] >= 1
    assert len(tokenizer.encode(value.text, add_special_tokens=True, truncation=False)) <= 512


def test_pinned_tokenizer_exactly_512_first_draft_is_not_shortened(monkeypatch):
    from app.retrieval import job_budget
    tokenizer = _pinned_tokenizer()
    base = job_budget._metadata(job(), tokenizer)
    body = None
    for word in ("data", "system", "test"):
        for n in range(513):
            candidate = "Source requirements: " + " ".join([word] * n)
            if len(tokenizer.encode(base + "\n" + candidate, add_special_tokens=True, truncation=False)) == 512:
                body = candidate
                break
        if body is not None:
            break
    assert body is not None, "Could not construct an exact pinned-tokenizer boundary fixture"
    original = job_budget._render_bucket
    initial_budget = None

    def exact_first_draft(kind, units, budget, tok):
        nonlocal initial_budget
        if initial_budget is None:
            initial_budget = budget
        if budget >= initial_budget:
            return body, [{"source_section_start": 0, "line": 0, "unit_index": 0,
                           "retained_characters": len(body), "original_characters": len(body)}]
        return original(kind, units, budget, tok)

    monkeypatch.setattr(job_budget, "_render_bucket", exact_first_draft)
    source = [{"section_type": "required_skills", "content": body, "start_char": 0}]
    first = job_representation_v2(job(), [], source, tokenizer)
    second = job_representation_v2(job(), [], source, tokenizer)
    assert first.details["initial_tokens"] == first.details["tokens"] == 512
    assert first.details["shrink_passes"] == 0
    assert first.text == base + "\n" + body
    assert first.text == second.text and first.source_hash == second.source_hash


def test_v1_outputs_match_recorded_head_bytes_and_hashes():
    # Captured from git-show HEAD at 8607310; baseline module SHA-256:
    # 90d083b46aea12014613a8350fe001e9f261104ee7713269f2d374f812e8b3d3.
    rows = [dict(id="2", text="Pending", status="pending", evidence="Ignore"),
            dict(id="1", text="C++", status="approved", evidence="Built software", canonical="Programming", release="v"),
            dict(id="3", text="Rejected", status="rejected", evidence="Ignore")]
    candidate = candidate_representation_v1(rows)
    assert candidate.text.encode() == b"query: Skills: C++; Programming\nEvidence: Built software"
    assert candidate.source_hash == "382b35512ac2fada755c94707c9475c6ce2034b04d8783c5480efe05fbabc29d"
    baseline = job_representation_v1(job(), terms())
    assert baseline.text.encode() == (b"passage: Job title: Engineer\nEmployment: full-time\nLocation: City\n"
        b"Required skills: Python; Python programming\nPreferred skills: SQL\nOther skills: Git\nDescription: Original source")
    assert baseline.source_hash == "0eb7ce4a6745ce6dfbf57380a41267ecfa22bf6012636c5b5375e49e466a6a84"
    assert candidate_representation_v1(list(reversed(rows))) == candidate
    assert job_representation_v1(job(), list(reversed(terms()))) == baseline
