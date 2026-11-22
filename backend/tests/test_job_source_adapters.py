"""Live job source adapters with recorded responses; no network."""
import io
import json
import urllib.error
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path

import pytest

from app.core.config import Settings
from app.job_sources.arbeitnow import API_URL as ARBEITNOW_URL, ArbeitnowAdapter
from app.job_sources.base import FetchReport, JobPosting
from app.job_sources.greenhouse import API_URL as GREENHOUSE_URL, GreenhouseAdapter
from app.job_sources.http import HttpJsonClient, SourceUnavailable
from app.job_sources.registry import build_adapters
from app.job_sources.selection import select_postings
from app.job_sources.text import detect_language, html_to_text, is_europe_or_remote

FIXTURES = Path(__file__).parent / "fixtures" / "job_sources"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class RecordedClient:
    """Serves recorded responses by (url, params); unknown URLs behave like a missing board."""

    def __init__(self, responses: dict) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        key = (url, tuple(sorted((params or {}).items())))
        if key not in self.responses:
            raise SourceUnavailable("HTTP 404 for test")
        return self.responses[key]


def arbeitnow_client() -> RecordedClient:
    return RecordedClient({
        (ARBEITNOW_URL, (("page", 1),)): fixture("arbeitnow_page1.json"),
        (ARBEITNOW_URL, (("page", 2),)): fixture("arbeitnow_page2.json"),
    })


def test_arbeitnow_follows_pages_and_maps_fields():
    client, report = arbeitnow_client(), FetchReport("arbeitnow")
    postings = list(ArbeitnowAdapter(max_pages=5).fetch(client, report))
    assert [call[1] for call in client.calls] == [{"page": 1}, {"page": 2}]  # stops when `next` is null
    assert report.fetched == 3 and report.requests == 2 and not report.errors
    first = postings[0]
    assert first.external_id == "backend-engineer-berlin-1001"
    assert first.external_url.startswith("https://www.arbeitnow.com/jobs/")
    assert first.posted_at == datetime.fromtimestamp(1795260657, tz=timezone.utc)
    assert first.company == "Example Payments GmbH" and first.location == "Berlin"
    assert "Requirements\n\n- Python\n- PostgreSQL\n- Docker\n\nQuestions?" in first.description
    assert postings[2].remote is True


def test_arbeitnow_respects_page_limit_and_reports_errors():
    client = arbeitnow_client()
    assert len(list(ArbeitnowAdapter(max_pages=1).fetch(client, FetchReport("arbeitnow")))) == 2
    report = FetchReport("arbeitnow")
    assert list(ArbeitnowAdapter().fetch(RecordedClient({}), report)) == []
    assert report.errors == ["page 1: HTTP 404 for test"]


def test_greenhouse_reads_each_board_with_content_and_skips_missing_boards():
    client = RecordedClient({(GREENHOUSE_URL.format(board="exampleco"), (("content", "true"),)):
                             fixture("greenhouse_exampleco.json")})
    report = FetchReport("greenhouse")
    postings = list(GreenhouseAdapter(["exampleco", "gone"]).fetch(client, report))
    assert report.fetched == 5 and report.requests == 1 and report.errors == ["gone: HTTP 404 for test"]
    analyst = postings[0]
    assert analyst.external_id == "exampleco:5001"  # IDs are unique per board
    assert analyst.external_url == "https://example.com/careers/5001?gh_jid=5001"
    assert analyst.location == "Amsterdam; Amsterdam, North Holland, Netherlands"
    assert analyst.employment_type == "Full time" and analyst.company == "ExampleCo"
    assert "<" not in analyst.description and "- SQL" in analyst.description  # escaped HTML decoded
    assert analyst.posted_at.isoformat() == "2026-11-10T07:42:40-04:00"
    assert postings[4].posted_at is not None  # falls back to updated_at
    assert postings[4].remote is True


def test_greenhouse_verify_keeps_only_working_tokens():
    client = RecordedClient({(GREENHOUSE_URL.format(board="exampleco"), ()): fixture("greenhouse_exampleco.json")})
    assert GreenhouseAdapter(["exampleco", "gone"]).verify(client) == {"exampleco": 5, "gone": "HTTP 404 for test"}


def test_language_check_and_location_filter():
    assert detect_language(html_to_text(fixture("greenhouse_exampleco.json")["jobs"][3]["content"])) == "de"
    assert detect_language("Backend Engineer") == "unknown"  # too short to decide
    assert is_europe_or_remote("Berlin, Berlin, Germany")
    assert is_europe_or_remote("Remote - EMEA")
    assert is_europe_or_remote("", remote=True)
    assert not is_europe_or_remote("Remote - US")
    assert not is_europe_or_remote("New York, New York, United States")
    assert is_europe_or_remote("New York; London, United Kingdom")


def _all_postings():
    gh = RecordedClient({(GREENHOUSE_URL.format(board="exampleco"), (("content", "true"),)):
                         fixture("greenhouse_exampleco.json")})
    return (list(ArbeitnowAdapter().fetch(arbeitnow_client(), FetchReport("a")))
            + list(GreenhouseAdapter(["exampleco"]).fetch(gh, FetchReport("g"))))


def test_selection_keeps_english_european_or_remote_postings_newest_first():
    selected, report = select_postings(_all_postings(), max_active=100, europe_only_sources=frozenset({"arbeitnow"}))
    assert [p.external_id for p in selected] == [
        "support-specialist-remote-1003", "backend-engineer-berlin-1001", "exampleco:5005", "exampleco:5001"]
    # The German postings (one declared "en" by the board) are skipped and counted by language.
    assert report.skipped_language == {"de": 2}
    assert report.skipped_location == 2  # New York and Remote - US
    assert report.considered == 8 and report.selected == 4 and report.over_cap == 0


def test_selection_cap_and_duplicates():
    postings = _all_postings()
    selected, report = select_postings(postings + postings[:1], max_active=2,
                                       europe_only_sources=frozenset({"arbeitnow"}))
    assert [p.external_id for p in selected] == ["support-specialist-remote-1003", "backend-engineer-berlin-1001"]
    assert report.over_cap == 2 and report.skipped_duplicate_id == 1
    # Filters can be switched off.
    everything, _ = select_postings(postings, 100, english_only=False, europe_or_remote_only=False)
    assert len(everything) == 8


def test_registry_reads_settings():
    config = Settings(LIVE_JOB_SOURCES="greenhouse", GREENHOUSE_BOARDS='["a", "b"]')
    (adapter,) = build_adapters(config)
    assert adapter.name == "greenhouse" and adapter.boards == ["a", "b"]
    assert [a.name for a in build_adapters(Settings())] == ["arbeitnow", "greenhouse"]
    assert len(Settings().greenhouse_boards) == 20
    with pytest.raises(ValueError, match="Unknown live job source"):
        build_adapters(Settings(LIVE_JOB_SOURCES="scraper"))


def _http_error(code, retry_after=None):
    headers = Message()
    if retry_after:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://api.example/x", code, "error", headers, io.BytesIO(b""))


def test_http_client_paces_requests_and_retries_rate_limits(monkeypatch):
    sleeps, now = [], [100.0]
    responses = [_http_error(429, "7"), io.BytesIO(b'{"ok": 1}'), io.BytesIO(b'{"ok": 2}')]

    def fake_urlopen(request, timeout):
        assert request.get_header("User-agent") == "test-agent"
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = HttpJsonClient("test-agent", min_interval=1.5, sleep=lambda s: sleeps.append(s), clock=lambda: now[0])
    assert client.get_json("https://api.example/x", {"page": 1}) == {"ok": 1}
    assert client.get_json("https://api.example/x") == {"ok": 2}
    # Retry-After honoured, then the per-host interval before each further request.
    assert sleeps == [7.0, 1.5, 1.5]


def test_http_client_gives_up_cleanly(monkeypatch):
    def not_found(request, timeout):
        raise _http_error(404)
    monkeypatch.setattr("urllib.request.urlopen", not_found)
    with pytest.raises(SourceUnavailable, match="HTTP 404"):
        HttpJsonClient("ua", min_interval=0, sleep=lambda s: None).get_json("https://api.example/missing")


def test_job_read_carries_attribution_only_for_live_sources():
    from uuid import uuid4

    from app.schemas.documents import JobRead
    base = dict(id=uuid4(), title="t", company="c", location="", employment_type="", description="d",
                cleaned_description="d", status="processed", error_message="", processed_at=None)
    live = JobRead(**base, source="arbeitnow", external_url="https://www.arbeitnow.com/jobs/x")
    assert live.model_dump()["attribution"] == {"name": "Arbeitnow", "url": "https://www.arbeitnow.com/"}
    assert JobRead(**base, source="greenhouse").attribution["name"] == "Greenhouse job board"
    assert JobRead(**base, source="manual").attribution is None
    assert JobRead(**base, source="evaluation").attribution is None


def test_allocate_respects_share_and_fills_with_other_sources():
    from app.job_sources.selection import allocate, source_limit
    items = [("a", 9), ("a", 8), ("a", 7), ("a", 6), ("b", 5), ("b", 1)]
    kept, over_share, over_cap = allocate(items, 4, 0.5, lambda i: i[0], lambda i: (i[1],))
    assert kept == [("a", 9), ("a", 8), ("b", 5), ("b", 1)] and over_share == [("a", 7), ("a", 6)] and over_cap == []
    kept, over_share, over_cap = allocate(items, 3, 1.0, lambda i: i[0], lambda i: (i[1],))
    assert kept == [("a", 9), ("a", 8), ("a", 7)] and over_cap == [("a", 6), ("b", 5), ("b", 1)]
    assert source_limit(1000, 0.7) == 700 and source_limit(1, 0.5) == 1 and source_limit(10, 1.0) == 10
