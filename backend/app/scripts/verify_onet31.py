"""Full CSV round-trip/replacement verification in a disposable phase4_verify schema."""
import argparse
import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from zipfile import ZipFile

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import TaxonomyConcept, TaxonomyRelationship, TaxonomyVersion, Occupation
from app.db.models.taxonomy import OnetDataRecord
from app.services.taxonomy_service import TaxonomyService
from app.taxonomy.onet_31 import MANIFEST, record_key
from app.scripts.verify_taxonomy_package import package_bytes


def row_hash(row):
    return sha256(json.dumps(row, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def reconcile(engine, content):
    """Compare every persisted source field, not just counts, in a fresh session."""
    with Session(engine) as db, ZipFile(io.BytesIO(content)) as archive:
        version = db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.version == "31.0"))
        report = dict(version.import_report)
        members = {name.rsplit("/", 1)[-1]: name for name in archive.namelist() if not name.endswith("/")}
        for filename, expected in report["datasets"].items():
            with archive.open(members[filename]) as stream:
                source = {record_key(filename, row): row_hash(row)
                          for row in csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))}
            actual = 0
            query = select(OnetDataRecord.record_key, OnetDataRecord.source_data).where(
                OnetDataRecord.taxonomy_version_id == version.id, OnetDataRecord.dataset == filename)
            for key, row in db.execute(query.execution_options(yield_per=1000)):
                assert source.pop(key) == row_hash(row), (filename, key)
                actual += 1
            assert not source
            assert actual == expected["input"] == expected["inserted"], (filename, actual, expected)
            expected.update(verified_database_count=actual, all_source_fields_equal=True)
        relations = list(db.scalars(select(TaxonomyRelationship).where(TaxonomyRelationship.taxonomy_version_id == version.id)))
        concepts = dict(db.execute(select(TaxonomyConcept.id, TaxonomyConcept.external_id).where(TaxonomyConcept.taxonomy_version_id == version.id)).all())
        for relation in relations:
            row = relation.metadata_json["source"]
            columns = [c for c in MANIFEST["datasets"][relation.metadata_json["dataset"]]["headers"] if c.endswith("Element ID")]
            expected = (tuple(row[c] for c in columns) if columns else
                        ("ONET:" + row["O*NET-SOC Code"], "ONET:" + row["Related O*NET-SOC Code"]))
            assert (concepts[relation.source_concept_id], concepts[relation.target_concept_id]) == expected
        assert len(relations) == report["relationships_resolved"]
        report["database_checks"] = dict(concepts=len(concepts),
            occupations=db.scalar(select(func.count()).select_from(Occupation).where(Occupation.taxonomy_version_id == version.id)),
            relationships=len(relations), all_relationship_directions_verified=True,
            relationship_types=dict(Counter(r.relationship_type for r in relations)),
            negative_wi_rows=db.scalar(select(func.count()).select_from(OnetDataRecord).where(
                OnetDataRecord.taxonomy_version_id == version.id, OnetDataRecord.scale_id == "WI", OnetDataRecord.numeric_value < 0)))
        report["migration_revision"] = db.scalar(text("select version_num from alembic_version"))
        report["postgresql_version"] = db.scalar(text("select version()"))
        return version.id, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = make_url(settings.DATABASE_URL)
    if url.database != "phase4_verify" or url.get_backend_name() != "postgresql" or url.query.get("options"):
        parser.error("Requires isolated PostgreSQL phase4_verify without a preselected schema")
    content = package_bytes(args.package)
    assert sha256(content).hexdigest() == MANIFEST["archive_sha256"], "Expected inspected official archive"
    admin = create_engine(url)
    schema = "onet31_verify_" + uuid4().hex
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    previous = settings.DATABASE_URL
    started = perf_counter()
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        settings.DATABASE_URL = scoped.render_as_string(hide_password=False)
        command.upgrade(Config("alembic.ini"), "head")
        runs = []
        old_id = None
        for stage in ("initial_import", "same_version_replacement"):
            tick = perf_counter()
            with Session(engine) as db:
                TaxonomyService(db).import_release("ONET", "31.0", "2026-08", args.package.name, content)
            version_id, report = reconcile(engine, content)
            if old_id:
                with Session(engine) as db:
                    assert db.get(TaxonomyVersion, old_id) is None
                    assert db.scalar(select(func.count()).select_from(TaxonomyVersion)) == 1
                assert version_id != old_id
            runs.append(dict(stage=stage, all_datasets_reconciled=True, all_source_fields_equal=True,
                             elapsed_seconds=round(perf_counter() - tick, 3)))
            print(json.dumps(runs[-1]), flush=True)
            old_id = version_id
        report.update(verified=True, source="ONET", version="31.0",
            supplied_archive=str(args.package.name), archive_reconstructed_from_directory=False,
            provenance="User-supplied official O*NET 31.0 CSV ZIP; embedded Read Me.txt identifies August 2026",
            verified_at=datetime.now(timezone.utc).isoformat(), runs=runs,
            replacement_verified=True, elapsed_seconds=round(perf_counter() - started, 3),
            isolated_schema_removed=True)
    finally:
        settings.DATABASE_URL = previous
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({"verified": True, "output": str(args.output), "elapsed_seconds": report["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
