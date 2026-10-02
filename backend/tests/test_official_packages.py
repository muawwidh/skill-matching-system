from dataclasses import replace
from decimal import Decimal
import csv
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from sqlalchemy import func, select

from app.db.models import Occupation, TaxonomyConcept, TaxonomyRelationship, TaxonomyVersion
from app.db.models.taxonomy import OnetDataRecord
from app.services.taxonomy_service import TaxonomyService
from app.taxonomy.importer import TaxonomyFileParser
from app.taxonomy.packages import ArchiveLimits, OfficialPackageParser, read_archive
from test_taxonomy import register, grant_researcher


FIXTURES = Path(__file__).parent / "fixtures" / "taxonomy"


def fixture_files(source: str) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in (FIXTURES / source.lower()).iterdir() if path.is_file()}


def archive(files: dict[str, bytes]) -> bytes:
    result = BytesIO()
    with ZipFile(result, "w", compression=ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return result.getvalue()


@pytest.mark.parametrize("source,version", [("ESCO", "1.2.1"), ("ONET", "29.0")])
def test_native_package_persistence(db_session, source, version):
    result = TaxonomyService(db_session).import_release(source, version, "", "fixture.zip",
                                                       archive(fixture_files(source)), is_sample=True)
    assert result.import_report["unresolved_references"] == []
    assert all(item["input"] == item["inserted"] > 0 for item in result.import_report["datasets"].values())
    version_record = db_session.scalar(select(TaxonomyVersion))
    assert version_record.is_sample
    assert version_record.import_report["sha256"] == result.import_report["sha256"]
    if source == "ESCO":
        links = list(db_session.scalars(select(TaxonomyRelationship)))
        assert len(links) == 6
        assert {item.relationship_type for item in links} == {"broader", "essential", "optional"}
        for item in links:
            a = db_session.get(TaxonomyConcept, item.source_concept_id)
            b = db_session.get(TaxonomyConcept, item.target_concept_id)
            row = item.metadata_json["source"]
            assert a.external_id == row.get("conceptUri", row.get("occupationUri", row.get("originalSkillUri")))
            assert b.external_id == row.get("broaderUri", row.get("skillUri", row.get("relatedSkillUri")))
            assert a.taxonomy_version_id == b.taxonomy_version_id == item.taxonomy_version_id
    else:
        occupation = db_session.scalar(select(Occupation))
        assert occupation.code == "11-1011.00"
        assert occupation.job_zone == 5
        assert occupation.concept.labels
        skills = list(db_session.scalars(select(OnetDataRecord).where(OnetDataRecord.dataset == "Skills.txt")))
        assert {item.scale_id for item in skills} == {"IM", "LV"}
        assert all(item.numeric_value == Decimal(item.source_data["Data Value"]) for item in skills)
        assert db_session.scalar(select(func.count()).select_from(OnetDataRecord)) == result.structured_records_imported


@pytest.mark.parametrize("name", ["Alternate Titles.txt", "Job Zones.txt", "Job Zone Reference.txt"])
def test_optional_onet_files_are_ingested_and_validated(name):
    files = fixture_files("ONET")
    package = OfficialPackageParser().parse(archive(files), "ONET", "29.0")
    assert any(item["dataset"] == name for item in package.records)
    files[name] = b"invalid\nvalue\n"
    with pytest.raises(ValueError, match="missing required columns"):
        OfficialPackageParser().parse(archive(files), "ONET", "29.0")


def test_optional_onet_absence_and_unknown_files():
    files = fixture_files("ONET")
    for name in ("Alternate Titles.txt", "Job Zones.txt", "Job Zone Reference.txt"):
        del files[name]
    files["Read Me.txt"] = b"O*NET 29.0 Database"
    package = OfficialPackageParser().parse(archive(files), "ONET", "29.0")
    assert len(package.report["missing_optional_files"]) == 3
    assert package.report["skipped_files"] == ["Read Me.txt"]


@pytest.mark.parametrize("source,version", [("ESCO", "1.2.1"), ("ONET", "29.0")])
def test_required_files_headers_versions_references(source, version):
    files = fixture_files(source)
    name = "skills_en.csv" if source == "ESCO" else "Skills.txt"
    with pytest.raises(ValueError, match="Missing required package files"):
        OfficialPackageParser().parse(archive({k: v for k, v in files.items() if k != name}), source, version)
    with pytest.raises(ValueError, match="missing required columns"):
        OfficialPackageParser().parse(archive({**files, name: b"invalid\nvalue\n"}), source, version)
    with pytest.raises(ValueError, match="Supported package contract"):
        OfficialPackageParser().parse(archive(files), source, "1.2.0" if source == "ESCO" else "30.0")
    if source == "ONET":
        files[name] = files[name].replace(b"11-1011.00", b"00-0000.00")
    else:
        files[name] = files[name].split(b"\n", 1)[0] + b"\n"
    with pytest.raises(ValueError, match="unresolved"):
        OfficialPackageParser().parse(archive(files), source, version)


@pytest.mark.parametrize("limit", ["upload", "total", "member", "count"])
def test_archive_safety_limits(limit):
    content = archive({"a.txt": b"a" * 2000, "b.txt": b"b" * 2000})
    limits = replace(ArchiveLimits(), **{limit: 1})
    with pytest.raises(ValueError, match="limit"):
        read_archive(content, limits)


@pytest.mark.parametrize("name", ["../a.csv", "/a.csv", "a\\b.csv", "C:a.csv"])
def test_archive_unsafe_paths(name):
    with pytest.raises(ValueError, match="Unsafe"):
        read_archive(archive({name: b"x"}))


def test_archive_duplicate_names_symlinks_and_corruption():
    with pytest.raises(ValueError, match="duplicate"):
        read_archive(archive({"a/file.txt": b"a", "b/file.txt": b"b"}))
    buf = BytesIO()
    with ZipFile(buf, "w") as z:
        info = ZipInfo("link")
        info.external_attr = 0o120777 << 16
        z.writestr(info, "/tmp/target")
    with pytest.raises(ValueError, match="Unsafe"):
        read_archive(buf.getvalue())
    with pytest.raises(ValueError, match="Invalid taxonomy ZIP"):
        read_archive(b"not a zip")


@pytest.mark.parametrize("extension,separator", [("csv", ","), ("tsv", "\t"), ("txt", "\t")])
def test_legacy_delimited_adapter(extension, separator):
    content = f"external_id{separator}preferred_label\nx{separator}Python\n".encode()
    assert TaxonomyFileParser().parse(f"sample.{extension}", content, "ESCO").concepts[0].preferred_label == "Python"


def test_official_import_permissions_and_read_access(client, db_session):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    content = archive(fixture_files("ESCO"))
    assert client.post("/taxonomy/import/esco", headers=headers,
        data={"version": "1.2.1"}, files={"file": ("fixture.zip", content)}).status_code == 403
    grant_researcher(db_session)
    assert client.post("/taxonomy/import/esco", headers=headers,
        data={"version": "1.2.1"}, files={"file": ("fixture.zip", content)}).status_code == 200
    candidate = register(client, "read-only@example.com")
    headers = {"Authorization": f"Bearer {candidate}"}
    concept = db_session.scalar(select(TaxonomyConcept))
    assert client.get(f"/taxonomy/concepts/{concept.id}/relationships", headers=headers).status_code == 200
    assert client.get("/taxonomy/versions", headers=headers).status_code == 200


def rewrite_csv(content: bytes, transform) -> bytes:
    reader = csv.DictReader(StringIO(content.decode()))
    data = list(reader)
    transform(data)
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(data)
    return out.getvalue().encode()


def test_esco_timestamp_only_duplicates_preserved_conflicts_rejected(db_session):
    files = fixture_files("ESCO")
    filename = "skills_en.csv"
    files[filename] = rewrite_csv(files[filename], lambda rows: rows.append({**rows[0], "modifiedDate": "2025-11-26T10:00:00Z"}))
    result = TaxonomyService(db_session).import_release("ESCO", "1.2.1", "", "fixture.zip", archive(files))
    counts = result.import_report["datasets"][filename]
    assert counts["input"] == counts["inserted"] + counts["merged_duplicate_rows"]
    assert counts["merged_duplicate_rows"] == 1
    concepts = list(db_session.scalars(select(TaxonomyConcept)))
    assert any(len(item.metadata_json.get("source_rows", [])) == 2 for item in concepts)
    files[filename] = rewrite_csv(files[filename], lambda rows: rows[-1].update(preferredLabel="Conflicting label"))
    with pytest.raises(ValueError, match="Conflicting"):
        OfficialPackageParser().parse(archive(files), "ESCO", "1.2.1")


def test_archive_runtime_limits_even_if_declared_sizes_are_small(monkeypatch):
    import app.taxonomy.packages as packages

    class Member:
        filename = "file.txt"
        file_size = 1
        flag_bits = 0
        external_attr = 0

        def is_dir(self):
            return False

    class FakeArchive:
        def __init__(self, content):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def infolist(self):
            return [Member()]

        def open(self, member):
            return BytesIO(b"x" * 1024)

    monkeypatch.setattr(packages, "ZipFile", FakeArchive)
    for limits in (replace(ArchiveLimits(), total=100), replace(ArchiveLimits(), member=100)):
        with pytest.raises(ValueError, match="runtime uncompressed"):
            read_archive(b"small upload", limits)


@pytest.mark.parametrize("replacement", [b"NaN", b"infinity", b"999.00", b"not-a-number"])
def test_onet_bad_rating_values(replacement):
    files = fixture_files("ONET")
    lines = files["Skills.txt"].splitlines()
    fields = lines[1].split(b"\t")
    fields[4] = replacement
    lines[1] = b"\t".join(fields)
    files["Skills.txt"] = b"\n".join(lines) + b"\n"
    with pytest.raises(ValueError, match="numeric|outside scale"):
        OfficialPackageParser().parse(archive(files), "ONET", "29.0")


def test_candidate_all_management_endpoints_forbidden(client):
    from uuid import uuid4
    token = register(client, "no-management@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    for path in ("esco", "onet", "mappings"):
        response = client.post(f"/taxonomy/import/{path}", headers=headers, data={"version": "29.0"},
                               files={"file": ("fixture.zip", archive(fixture_files("ONET")))})
        assert response.status_code == 403
    assert client.post("/taxonomy/import/sample", headers=headers).status_code == 403
    assert client.post("/taxonomy/link", headers=headers,
                       json={"term_source": "candidate", "document_id": str(uuid4())}).status_code == 403
    assert client.put(f"/taxonomy/link/{uuid4()}/approve", headers=headers,
                      json={"status": "approved"}).status_code == 403
    assert client.get("/admin/mappings/review", headers=headers).status_code == 403
    for path in ("/taxonomy/search?q=Python", "/taxonomy/versions", "/taxonomy/mappings"):
        assert client.get(path, headers=headers).status_code == 200
