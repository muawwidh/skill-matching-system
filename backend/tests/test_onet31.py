import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TaxonomyConcept, TaxonomyVersion
from app.db.models.taxonomy import OnetDataRecord, TaxonomyRelationship
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.services.taxonomy_service import TaxonomyService
from app.taxonomy.onet_31 import MANIFEST, record_key
from app.taxonomy.packages import ArchiveLimits, OfficialPackageParser, read_archive
from test_official_packages import archive
from test_taxonomy_postgres import pg_database, snapshot  # noqa: F401


def fixture_tables():
    return json.loads((Path(__file__).parent / "fixtures/onet31/representative.json").read_text())


def files_for(tables=None):
    tables = fixture_tables() if tables is None else tables
    result = {"Read Me.txt": b"O*NET 31.0 Database\nAugust 2026 Release"}
    for name, table in tables.items():
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=MANIFEST["datasets"][name]["headers"])
        writer.writeheader()
        writer.writerows(table)
        result[name] = output.getvalue().encode("utf-8-sig")
    return result


def parse(files=None):
    return OfficialPackageParser().parse(archive(files or files_for()), "ONET", "31.0")


def test_all_datasets_lossless_and_relationship_direction():
    tables = fixture_tables()
    package = parse()
    assert set(package.report["datasets"]) == set(MANIFEST["datasets"])
    for name, original in tables.items():
        assert [r["source_data"] for r in package.records if r["dataset"] == name] == original
    relation = next(r for r in package.relationships if r["relationship_type"] == "essential_skills_to_work_activities")
    assert relation["source"] == relation["metadata_json"]["source"]["Essential Skills Element ID"]
    assert relation["target"] == relation["metadata_json"]["source"]["Work Activities Element ID"]
    assert any(r["scale_id"] == "WI" and r["numeric_value"] is not None and r["numeric_value"] < 0 for r in package.records)
    assert {r["scale_id"] for r in package.records if r["dataset"] == "education_categories.csv"} == {"RL", "RQ"}
    assert any(r["dataset"] == "gwas_to_iwas_to_dwas.csv" and "IWA Element ID" in r["source_data"] for r in package.records)


@pytest.mark.parametrize("name", MANIFEST["datasets"])
def test_each_required_dataset_and_header(name):
    files = files_for()
    del files[name]
    with pytest.raises(ValueError, match="missing required files"):
        parse(files)
    files = files_for()
    files[name] = files[name].replace(MANIFEST["datasets"][name]["headers"][0].encode(), b"wrong", 1)
    with pytest.raises(ValueError, match="missing required columns"):
        parse(files)


def test_version_encoding_quoting_extra_columns_and_unknown_files():
    tables = fixture_tables()
    tables["occupation_data.csv"][0]["Description"] = 'Quoted "text", with\nUnicode: caf\u00e9'
    files = files_for(tables)
    files["unknown.csv"] = b"a,b\n1,2"
    package = parse(files)
    assert next(r["source_data"]["Description"] for r in package.records if r["dataset"] == "occupation_data.csv") == tables["occupation_data.csv"][0]["Description"]
    assert "unknown.csv" in parse(files).report["skipped_files"]
    files["Read Me.txt"] = b"O*NET 29.0 Database"
    with pytest.raises(ValueError, match="disagrees"):
        parse(files)
    files = files_for()
    files["occupation_data.csv"] += b"\xff"
    with pytest.raises(UnicodeDecodeError):
        parse(files)
    with pytest.raises(ValueError):
        OfficialPackageParser().parse(archive(files_for()), "ONET", "29.0")


def test_extra_columns_are_preserved_and_blank_readme_rejected():
    files = files_for()
    table = fixture_tables()["occupation_data.csv"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[*table[0], "Additional provenance"])
    writer.writeheader()
    writer.writerows([{**row, "Additional provenance": "unchanged source text"} for row in table])
    files["occupation_data.csv"] = output.getvalue().encode()
    package = parse(files)
    assert all(r["source_data"]["Additional provenance"] == "unchanged source text"
               for r in package.records if r["dataset"] == "occupation_data.csv")
    files["Read Me.txt"] = b""
    with pytest.raises(ValueError, match="disagrees"):
        parse(files)


@pytest.mark.parametrize("content", [b"O*NET-SOC Code,Title,Title\n", b'O*NET-SOC Code,Title,Description\n"unterminated',
                                     b"O*NET-SOC Code,Title,Description\n11-1011.00,missing-column\n"])
def test_malformed_csv(content):
    files = files_for()
    files["occupation_data.csv"] = content
    with pytest.raises((ValueError, csv.Error)):
        parse(files)


@pytest.mark.parametrize("dataset,column,value", [
    ("essential_skills.csv", "Element ID", "missing"),
    ("software_skills.csv", "O*NET-SOC Code", "missing"),
    ("work_styles.csv", "Scale ID", "missing"),
    ("work_styles.csv", "Data Value", "-99"),
    ("education.csv", "Category", "999"),
    ("task_ratings.csv", "Task ID", "missing"),
    ("gwas_to_iwas_to_dwas.csv", "IWA Element ID", "missing"),
])
def test_invalid_references_scales_categories(dataset, column, value):
    tables = fixture_tables()
    tables[dataset][0][column] = value
    with pytest.raises(ValueError):
        parse(files_for(tables))


def test_duplicate_rows_members_malformed_and_limits():
    tables = fixture_tables()
    tables["software_skills.csv"].append(dict(tables["software_skills.csv"][0]))
    with pytest.raises(ValueError, match="duplicate record identity"):
        parse(files_for(tables))
    files = files_for()
    files["nested/occupation_data.csv"] = files["occupation_data.csv"]
    with pytest.raises(ValueError, match="duplicate archive"):
        parse(files)
    with pytest.raises(ValueError):
        read_archive(b"not a zip")
    content = archive(files_for())
    for limits in (ArchiveLimits(count=1), ArchiveLimits(member=1), ArchiveLimits(total=1), ArchiveLimits(upload=1)):
        with pytest.raises(ValueError):
            read_archive(content, limits)


def test_full_archive_collision_regression():
    path = Path(__file__).resolve().parents[2] / "db_31_0_csv.zip"
    if not path.exists():
        pytest.skip("UNVERIFIED: supplied full 31.0 package unavailable")
    old_columns = ["O*NET-SOC Code", "Element ID", "Scale ID", "Task ID", "Category", "Example",
                   "Commodity Code", "Alternate Title", "Short Title", "Source(s)", "Job Zone"]
    with ZipFile(path) as zipped:
        for name, collisions in (("software_skills.csv", 19137), ("essential_skills_to_work_activities.csv", 109)):
            table = list(csv.DictReader(io.TextIOWrapper(zipped.open("db_31_0_csv/" + name), encoding="utf-8-sig")))
            assert len(table) - len({tuple(row.get(c, "") for c in old_columns) for row in table}) == collisions
            assert len({record_key(name, row) for row in table}) == len(table)


def test_postgres_replacement_and_post_write_rollback(pg_database, monkeypatch):
    engine, _, _ = pg_database
    content = archive(files_for())
    with Session(engine) as db:
        service = TaxonomyService(db)
        service.import_release("ONET", "31.0", "", "fixture.zip", content)
        old = db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.version == "31.0")).id
        # Reviewed links must be restored on failed replacement and removed on success.
        repo = TaxonomyRepository(db)
        concept = db.scalar(select(TaxonomyConcept).where(TaxonomyConcept.taxonomy_version_id == old))
        from uuid import uuid4
        candidate = repo.add_link_candidate("candidate", uuid4(), "test", "test", concept.id, "fuzzy", .8, 1, "pending")
        repo.approve_candidate(candidate, "test", None)
        db.commit()
    with engine.connect() as connection:
        before = snapshot(connection)
    original = TaxonomyRepository._insert_batches
    def fail(self, model, records):
        original(self, model, records)
        if model is OnetDataRecord:
            raise RuntimeError("injected after writes")
    with monkeypatch.context() as patch:
        patch.setattr(TaxonomyRepository, "_insert_batches", fail)
        with Session(engine) as db, pytest.raises(RuntimeError, match="after writes"):
            TaxonomyService(db).import_release("ONET", "31.0", "", "fixture.zip", content)
    with engine.connect() as connection:
        assert snapshot(connection) == before
    with Session(engine) as db:
        TaxonomyService(db).import_release("ONET", "31.0", "", "fixture.zip", content)
    with Session(engine) as db:
        assert db.get(TaxonomyVersion, old) is None
        version = db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.version == "31.0"))
        assert db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.version == "29.0")).status == "inactive"
        records = list(db.scalars(select(OnetDataRecord).where(OnetDataRecord.taxonomy_version_id == version.id)))
        assert len(records) == sum(len(rs) for rs in fixture_tables().values())
        assert db.scalar(select(TaxonomyRelationship).where(TaxonomyRelationship.taxonomy_version_id == version.id))
