"""Opt-in PostgreSQL checks; isolated schemas, never the development database."""
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ApprovedTaxonomyLink, Occupation, TaxonomyConcept, TaxonomyRelationship, TaxonomyVersion, User
from app.db.models.taxonomy import OnetDataRecord
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.services.taxonomy_service import TaxonomyService
from test_official_packages import archive, fixture_files


def snapshot(connection):
    metadata = MetaData()
    metadata.reflect(connection)
    return {name: sorted((str(dict(row)) for row in connection.execute(select(table)).mappings()))
            for name, table in metadata.tables.items() if name != "alembic_version"}


def seed_0005(connection):
    """Use reflected 0005 tables, not newer ORM models, to test a real upgrade."""
    metadata = MetaData()
    metadata.reflect(connection)
    now = datetime.now(timezone.utc)

    def add(table, **values):
        values.setdefault("id", uuid4())
        connection.execute(insert(metadata.tables[table]).values(**values))
        return values["id"]

    user = add("users", email="postgres-review@example.com", full_name="Reviewer", hashed_password="unused",
               status="active", source="test")
    concepts, versions = [], []
    for source, version in (("ESCO", "1.2.1"), ("ONET", "29.0")):
        sid = add("taxonomy_sources", code=source, name=source, homepage_url="", description="")
        vid = add("taxonomy_versions", source_id=sid, version=version, release_date="", import_filename="seed.json",
                  checksum="0" * 64, status="active", is_sample=True, imported_at=now)
        versions.append(vid)
        cid = add("taxonomy_concepts", taxonomy_version_id=vid, external_id=f"seed:{source}",
                  preferred_label="Python", normalized_label="python", description="", concept_type="skill",
                  language="en", metadata_json={})
        concepts.append(cid)
        add("taxonomy_labels", concept_id=cid, label="Python programming", normalized_label="python programming",
            label_type="alternative", language="en")
    second = add("taxonomy_concepts", taxonomy_version_id=versions[0], external_id="seed:parent",
                 preferred_label="Programming", normalized_label="programming", description="", concept_type="skill",
                 language="en", metadata_json={})
    add("taxonomy_relationships", source_concept_id=concepts[0], target_concept_id=second, relationship_type="broader")
    occupation = add("occupations", taxonomy_version_id=versions[1], concept_id=concepts[1], code="11-1011.00",
                     title="Chief Executives", description="", job_zone=5, metadata_json={})
    add("esco_onet_mappings", esco_concept_id=concepts[0], onet_occupation_id=occupation,
        mapping_type="related", confidence_score=1, source="seed", version="seed")
    for concept in concepts:
        term = uuid4()
        link = add("taxonomy_link_candidates", term_source="candidate", extracted_term_id=term, raw_text="Python",
                   normalized_text="python", concept_id=concept, match_method="exact_preferred", confidence_score=1,
                   rank=1, review_status="approved", reviewed_by=user, reviewed_at=now)
        add("approved_taxonomy_links", term_source="candidate", extracted_term_id=term, concept_id=concept,
            link_candidate_id=link, match_method="exact_preferred", confidence_score=1,
            approval_source="human_review", approved_by=user, approved_at=now)


@pytest.fixture
def pg_database(monkeypatch):
    url_text = os.environ.get("PHASE4_TEST_DATABASE_URL")
    if not url_text:
        pytest.skip("UNVERIFIED: PHASE4_TEST_DATABASE_URL is not set")
    url = make_url(url_text)
    if url.database != "phase4_verify":
        pytest.fail("PostgreSQL tests require an isolated database named phase4_verify")
    schema = "phase4_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "DATABASE_URL", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "0005_taxonomy_integration")
        with engine.begin() as connection:
            seed_0005(connection)
            before = snapshot(connection)
        command.upgrade(config, "head")
        yield engine, config, before
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_upgrade_populated_0005_preserves_data(pg_database):
    engine, config, before = pg_database
    with engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == "0007_taxonomy_review_audit"
        assert connection.scalar(text("select count(*) from esco_onet_mappings")) == 1
        assert connection.scalar(text("select count(*) from approved_taxonomy_links")) == 2
        assert connection.scalar(text("select count(*) from taxonomy_relationships where taxonomy_version_id is not null")) == 1
    command.downgrade(config, "0005_taxonomy_integration")
    with engine.connect() as connection:
        assert snapshot(connection) == before
    command.upgrade(config, "head")


@pytest.mark.parametrize("failure_model", [TaxonomyConcept, Occupation, OnetDataRecord])
def test_rollback_after_replacement_writes(pg_database, monkeypatch, failure_model):
    engine, _, _ = pg_database
    with engine.connect() as connection:
        before = snapshot(connection)
    original = TaxonomyRepository._insert_batches

    def injected(self, model, records):
        original(self, model, records)
        if model is failure_model:
            raise RuntimeError("injected after database writes")

    monkeypatch.setattr(TaxonomyRepository, "_insert_batches", injected)
    with Session(engine) as db:
        with pytest.raises(RuntimeError, match="after database writes"):
            TaxonomyService(db).import_release("ONET", "29.0", "", "fixture.zip", archive(fixture_files("ONET")))
    with engine.connect() as connection:
        assert snapshot(connection) == before


def test_same_version_replacement_cascades_and_constraints(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        service = TaxonomyService(db)
        content = archive(fixture_files("ESCO"))
        service.import_release("ESCO", "1.2.1", "", "fixture.zip", content)
        first = db.scalar(select(TaxonomyConcept.id).where(TaxonomyConcept.external_id.like("http:%")))
        service.import_release("ESCO", "1.2.1", "", "fixture.zip", content)
        assert db.get(TaxonomyConcept, first) is None
        assert db.scalar(text("select count(*) from esco_onet_mappings")) == 0
        assert db.scalar(text("select count(*) from approved_taxonomy_links")) == 1
        assert db.scalar(text("select count(*) from taxonomy_relationships")) == 6
        relation = db.scalar(select(TaxonomyRelationship))
        onet = db.scalar(select(TaxonomyConcept).where(TaxonomyConcept.external_id == "seed:ONET"))
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(insert(TaxonomyRelationship).values(id=uuid4(), taxonomy_version_id=relation.taxonomy_version_id,
                source_concept_id=relation.source_concept_id, target_concept_id=onet.id,
                relationship_type="cross-version", metadata_json={}))
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(insert(TaxonomyRelationship).values(id=uuid4(), taxonomy_version_id=relation.taxonomy_version_id,
                source_concept_id=relation.source_concept_id, target_concept_id=relation.target_concept_id,
                relationship_type=relation.relationship_type, metadata_json={}))
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(insert(OnetDataRecord).values(id=uuid4(), taxonomy_version_id=onet.taxonomy_version_id,
                occupation_code="nonexistent", dataset="Skills.txt", record_key="x", source_data={}))


def test_review_decisions_persist_in_postgres(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        repository = TaxonomyRepository(db)
        user = db.scalar(select(User))
        concept = db.scalar(select(TaxonomyConcept))
        candidates = [repository.add_link_candidate("candidate", uuid4(), "Pythn", "pythn", concept.id,
                                                   "fuzzy", 0.82, 1, "pending") for _ in range(2)]
        ids = [item.id for item in candidates]
        db.commit()
        service = TaxonomyService(db)
        service.review_link(ids[0], "approved", None, user)
        service.review_link(ids[1], "rejected", None, user)
    with Session(engine) as db:
        repository = TaxonomyRepository(db)
        assert repository.get_link_candidate(ids[0]).review_status == "approved"
        assert repository.get_link_candidate(ids[1]).review_status == "rejected"
        assert db.scalar(select(ApprovedTaxonomyLink).where(ApprovedTaxonomyLink.link_candidate_id == ids[0]))
        assert db.scalar(select(ApprovedTaxonomyLink).where(ApprovedTaxonomyLink.link_candidate_id == ids[1])) is None
