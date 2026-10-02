"""Run from backend: python -m app.scripts.verify_taxonomy_package --help."""
import argparse
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import perf_counter
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Occupation, TaxonomyConcept, TaxonomyRelationship, TaxonomyVersion
from app.db.models.taxonomy import OnetDataRecord
from app.services.taxonomy_service import TaxonomyService
from app.taxonomy.packages import LIMITS


def package_bytes(path: Path) -> bytes:
    if path.is_file():
        with path.open("rb") as stream:
            content = stream.read(LIMITS.upload + 1)
        if len(content) > LIMITS.upload:
            raise ValueError("Package upload size exceeded")
        return content
    files = sorted(path.iterdir())
    if len(files) > LIMITS.count:
        raise ValueError("Package file count exceeded")
    output = BytesIO()
    total = 0
    with ZipFile(output, "w") as archive:
        for file in files:
            if file.is_symlink() or not file.is_file():
                raise ValueError(f"Expected regular package file: {file.name}")
            with file.open("rb") as stream:
                content = stream.read(LIMITS.member + 1)
            total += len(content)
            if len(content) > LIMITS.member or total > LIMITS.total:
                raise ValueError("Package uncompressed size exceeded")
            info = ZipInfo(file.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-package checks in an isolated phase4_verify PostgreSQL database.")
    parser.add_argument("source", choices=["ESCO", "ONET"])
    parser.add_argument("version")
    parser.add_argument("package", type=Path)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = make_url(settings.DATABASE_URL)
    if url.database != "phase4_verify" or url.get_backend_name() != "postgresql":
        parser.error("Use an isolated PostgreSQL database named phase4_verify; development databases are refused.")
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    started = perf_counter()
    with Session(engine) as db:
        filename = args.package.name + ".zip" if args.package.is_dir() else args.package.name
        result = TaxonomyService(db).import_release(args.source, args.version, "", filename,
                                                   package_bytes(args.package))
    with Session(engine) as db:
        version = db.scalar(select(TaxonomyVersion).where(TaxonomyVersion.checksum == result.import_report["sha256"]))
        report = dict(version.import_report)
        counts = {}
        if args.source == "ONET":
            counts = dict(db.execute(select(OnetDataRecord.dataset, func.count()).where(
                OnetDataRecord.taxonomy_version_id == version.id).group_by(OnetDataRecord.dataset)).all())
        else:
            for model in (TaxonomyConcept, TaxonomyRelationship):
                dataset = model.metadata_json["dataset"].as_string()
                counts.update(dict(db.execute(select(dataset, func.count()).where(
                    model.taxonomy_version_id == version.id).group_by(dataset)).all()))
        for filename, expected in report["datasets"].items():
            actual = counts.get(filename, 0)
            assert expected["inserted"] == actual, (filename, expected, actual)
            assert expected["input"] == actual + expected["merged_duplicate_rows"], (filename, expected, actual)
            expected["verified_database_count"] = actual
        cross_version = db.scalar(text("""SELECT count(*) FROM taxonomy_relationships r
            JOIN taxonomy_concepts s ON r.source_concept_id=s.id
            JOIN taxonomy_concepts t ON r.target_concept_id=t.id
            WHERE r.taxonomy_version_id <> s.taxonomy_version_id OR r.taxonomy_version_id <> t.taxonomy_version_id"""))
        assert cross_version == 0
        checks = {"cross_version_relationships": cross_version,
                  "concepts": db.scalar(select(func.count()).select_from(TaxonomyConcept).where(TaxonomyConcept.taxonomy_version_id == version.id)),
                  "occupations": db.scalar(select(func.count()).select_from(Occupation).where(Occupation.taxonomy_version_id == version.id))}
        if args.source == "ESCO":
            checks["relationship_types"] = dict(db.execute(select(TaxonomyRelationship.relationship_type, func.count()).where(
                TaxonomyRelationship.taxonomy_version_id == version.id).group_by(TaxonomyRelationship.relationship_type)).all())
            checks["relationship_examples"] = [dict(row) for row in db.execute(text("""
                SELECT DISTINCT ON (r.relationship_type) r.relationship_type, s.external_id AS source_uri,
                    t.external_id AS target_uri, r.metadata_json
                FROM taxonomy_relationships r JOIN taxonomy_concepts s ON s.id=r.source_concept_id
                JOIN taxonomy_concepts t ON t.id=r.target_concept_id WHERE r.taxonomy_version_id=:version
                ORDER BY r.relationship_type, s.external_id, t.external_id"""), {"version": version.id}).mappings()]
        else:
            checks["rating_examples"] = [dict(row) for row in db.execute(text("""
                SELECT occupation_code, element_id, scale_id, numeric_value, source_data
                FROM onet_data_records WHERE taxonomy_version_id=:version AND dataset='Skills.txt'
                AND occupation_code='11-1011.00' ORDER BY element_id, scale_id LIMIT 2"""), {"version": version.id}).mappings()]
        report.update({"source": args.source, "version": args.version, "provenance": args.provenance,
                       "archive_reconstructed_from_directory": args.package.is_dir(),
                       "verified_at": datetime.now(timezone.utc).isoformat(),
                       "migration_revision": db.scalar(text("select version_num from alembic_version")),
                       "postgresql_version": db.scalar(text("select version()")),
                       "database_checks": checks, "elapsed_seconds": round(perf_counter() - started, 3),
                       "verified": True})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
        print(json.dumps({"verified": True, "report": str(args.output), "elapsed_seconds": report["elapsed_seconds"],
                          "input_records": sum(item["input"] for item in report["datasets"].values())}))
    engine.dispose()


if __name__ == "__main__":
    main()
