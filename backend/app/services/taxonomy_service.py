from pathlib import Path
from hashlib import sha256
import csv
from time import perf_counter
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import TaxonomyConcept, User
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.schemas.taxonomy import (
    TaxonomyReviewEventRead,
    TaxonomyReviewGroup,
    TaxonomyReviewPage,
    TaxonomySelectionRead,
    OnetDataRecordRead,
    TaxonomyRelationshipRead,
    EscoOnetMappingRead,
    OccupationRead,
    TaxonomyConceptRead,
    TaxonomyImportResult,
    TaxonomyLinkCandidateRead,
    TaxonomyLinkRunResult,
    TaxonomyVersionRead,
)
from app.taxonomy.importer import TaxonomyFileParser, normalized_alternatives
from app.taxonomy.linker import TaxonomyLinker
from app.taxonomy.normalization import normalize_taxonomy_text
from app.taxonomy.packages import LIMITS, OfficialPackageParser


SOURCE_DETAILS = {
    "ESCO": (
        "European Skills, Competences, Qualifications and Occupations",
        "https://esco.ec.europa.eu/",
        "European multilingual classification of skills and occupations.",
    ),
    "ONET": (
        "O*NET",
        "https://www.onetcenter.org/",
        "United States occupational information database.",
    ),
}


class TaxonomyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TaxonomyRepository(db)
        self.parser = TaxonomyFileParser()
        self.linker = TaxonomyLinker()

    def import_release(
        self, source_code: str, version: str, release_date: str, filename: str,
        content: bytes, is_sample: bool = False,
    ) -> TaxonomyImportResult:
        """Own the transaction, including rollback after replacement has begun."""
        try:
            return self._import_release(source_code, version, release_date, filename, content, is_sample)
        except Exception:
            self.db.rollback()
            raise

    def _import_release(
        self,
        source_code: str,
        version: str,
        release_date: str,
        filename: str,
        content: bytes,
        is_sample: bool = False,
    ) -> TaxonomyImportResult:
        source_code = source_code.upper()
        if source_code not in SOURCE_DETAILS:
            raise HTTPException(status_code=400, detail="Supported taxonomy sources are ESCO and ONET.")
        if not version.strip():
            raise HTTPException(status_code=400, detail="A taxonomy version is required.")
        started = perf_counter()
        package = None
        try:
            if len(content) > LIMITS.upload:
                raise ValueError("Taxonomy upload exceeds byte limit.")
            if Path(filename).suffix.lower() == ".zip":
                package = OfficialPackageParser().parse(content, source_code, version.strip())
                parsed = package.taxonomy
            else:
                parsed = self.parser.parse(filename, content, source_code)
        except (UnicodeDecodeError, ValueError, csv.Error) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not parsed.concepts and not parsed.occupations:
            raise HTTPException(status_code=400, detail="The import file contains no usable concepts or occupations.")

        name, homepage, description = SOURCE_DETAILS[source_code]
        self.repository.lock_source(source_code)
        source = self.repository.get_or_create_source(source_code, name, homepage, description)
        taxonomy_version = self.repository.replace_version(
            source=source,
            version=version.strip(),
            release_date=release_date.strip(),
            import_filename=filename,
            checksum=self.parser.checksum(content),
            is_sample=is_sample,
        )
        if package is not None:
            self.repository.persist_package(taxonomy_version, package)
            package.report["duration_seconds"] = round(perf_counter() - started, 3)
            taxonomy_version.import_report = dict(package.report)
            self.db.commit()
            return TaxonomyImportResult(
                source_code=source_code, version=version.strip(),
                concepts_imported=len(parsed.concepts) + len(parsed.occupations),
                occupations_imported=len(parsed.occupations), is_sample=is_sample,
                relationships_imported=len(package.relationships),
                structured_records_imported=len(package.records), import_report=package.report,
            )
        concepts_by_external_id: dict[str, TaxonomyConcept] = {}
        for record in parsed.concepts:
            concept = self.repository.add_concept(
                taxonomy_version_id=taxonomy_version.id,
                external_id=record.external_id,
                preferred_label=record.preferred_label,
                normalized_label=normalize_taxonomy_text(record.preferred_label),
                description=record.description,
                concept_type=record.concept_type,
                language=record.language,
                alternative_labels=normalized_alternatives(record.alternative_labels),
                metadata_json=record.metadata,
            )
            concepts_by_external_id[record.external_id] = concept

        for record in parsed.occupations:
            concept = self.repository.add_concept(
                taxonomy_version_id=taxonomy_version.id,
                external_id=record.external_id,
                preferred_label=record.title,
                normalized_label=normalize_taxonomy_text(record.title),
                description=record.description,
                concept_type="occupation",
                language="en",
                alternative_labels=normalized_alternatives(record.alternative_labels),
                metadata_json=record.metadata,
            )
            concepts_by_external_id[record.external_id] = concept
            self.repository.add_occupation(
                taxonomy_version_id=taxonomy_version.id,
                concept_id=concept.id,
                code=record.code,
                title=record.title,
                description=record.description,
                job_zone=record.job_zone,
                metadata_json=record.metadata,
            )
        self.db.commit()
        return TaxonomyImportResult(
            source_code=source_code,
            version=taxonomy_version.version,
            concepts_imported=len(parsed.concepts) + len(parsed.occupations),
            occupations_imported=len(parsed.occupations),
            is_sample=is_sample,
        )

    def import_mappings(self, version: str, filename: str, content: bytes) -> TaxonomyImportResult:
        try:
            parsed = self.parser.parse(filename, content, "ESCO")
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        imported = 0
        for record in parsed.mappings:
            concept = self.repository.find_concept_by_external_id(record.esco_external_id)
            occupation = self.repository.find_occupation_by_code(record.onet_code)
            if concept and occupation:
                self.repository.add_mapping(
                    concept.id,
                    occupation.id,
                    record.mapping_type,
                    record.confidence_score,
                    record.source,
                    version,
                )
                imported += 1
        self.db.commit()
        return TaxonomyImportResult(
            source_code="ESCO-ONET",
            version=version,
            concepts_imported=0,
            occupations_imported=0,
            mappings_imported=imported,
            is_sample=False,
        )

    def import_bundled_sample(self) -> list[TaxonomyImportResult]:
        data_path = Path(__file__).resolve().parents[3] / "data" / "sample"
        results = []
        for source_code, filename in (("ESCO", "esco_sample.json"), ("ONET", "onet_sample.json")):
            path = data_path / filename
            results.append(
                self.import_release(
                    source_code,
                    "sample-1.0",
                    "2026-09-22",
                    filename,
                    path.read_bytes(),
                    is_sample=True,
                )
            )
        mapping_path = data_path / "esco_onet_mappings_sample.json"
        mapping_result = self.import_mappings("sample-1.0", mapping_path.name, mapping_path.read_bytes())
        mapping_result.is_sample = True
        results.append(mapping_result)
        return results

    def search(self, query: str, source: str | None, concept_type: str | None, limit: int) -> list[TaxonomyConceptRead]:
        normalized = normalize_taxonomy_text(query)
        if len(normalized) < 2:
            return []
        return [self._concept_read(item) for item in self.repository.search_concepts(normalized, source, concept_type, min(limit, 100))]

    def get_concept(self, concept_id: UUID) -> TaxonomyConceptRead:
        concept = self.repository.get_concept(concept_id)
        if not concept:
            raise HTTPException(status_code=404, detail="Taxonomy concept not found.")
        return self._concept_read(concept)

    def relationships(self, concept_id: UUID, limit: int, offset: int) -> list[TaxonomyRelationshipRead]:
        self.get_concept(concept_id)
        return [TaxonomyRelationshipRead.model_validate(item)
                for item in self.repository.concept_relationships(concept_id, limit, offset)]

    def occupation_data(self, occupation_id: UUID, limit: int, offset: int) -> list[OnetDataRecordRead]:
        occupation = self.repository.get_occupation(occupation_id)
        if not occupation:
            raise HTTPException(status_code=404, detail="Occupation not found.")
        return [OnetDataRecordRead.model_validate(item)
                for item in self.repository.occupation_records(occupation, limit, offset)]

    def get_occupation(self, occupation_id: UUID) -> OccupationRead:
        occupation = self.repository.get_occupation(occupation_id)
        if not occupation:
            raise HTTPException(status_code=404, detail="Occupation not found.")
        return OccupationRead(
            id=occupation.id,
            code=occupation.code,
            title=occupation.title,
            description=occupation.description,
            job_zone=occupation.job_zone,
            source_code=occupation.taxonomy_version.source.code,
            taxonomy_version=occupation.taxonomy_version.version,
        )

    def list_versions(self) -> list[TaxonomyVersionRead]:
        return [
            TaxonomyVersionRead(
                id=item.id,
                version=item.version,
                release_date=item.release_date,
                import_filename=item.import_filename,
                status=item.status,
                is_sample=item.is_sample,
                imported_at=item.imported_at,
                source_code=item.source.code,
                source_name=item.source.name,
                checksum=item.checksum,
                import_report=item.import_report,
            )
            for item in self.repository.list_versions()
        ]

    def list_mappings(self) -> list[EscoOnetMappingRead]:
        return [
            EscoOnetMappingRead(
                id=item.id,
                esco_concept_id=item.esco_concept_id,
                esco_label=item.esco_concept.preferred_label,
                onet_occupation_id=item.onet_occupation_id,
                onet_code=item.onet_occupation.code,
                onet_title=item.onet_occupation.title,
                mapping_type=item.mapping_type,
                confidence_score=item.confidence_score,
                source=item.source,
                version=item.version,
            )
            for item in self.repository.list_mappings()
        ]

    def link_document(self, term_source: str, document_id: UUID) -> TaxonomyLinkRunResult:
        concepts = self.repository.active_concepts()
        if not concepts:
            raise HTTPException(status_code=409, detail="Import an ESCO or O*NET taxonomy release before linking terms.")
        terms = (
            self.repository.candidate_terms_for_document(document_id)
            if term_source == "candidate"
            else self.repository.job_terms_for_document(document_id)
        )
        candidates_created = 0
        auto_approved = 0
        for term in terms:
            self.repository.replace_link_candidates(term_source, term.id)
            ranked = self.linker.rank(term.normalized_text, concepts)
            for rank, result in enumerate(ranked, start=1):
                should_auto_approve = rank == 1 and result.confidence >= 0.95
                candidate = self.repository.add_link_candidate(
                    term_source=term_source,
                    extracted_term_id=term.id,
                    raw_text=term.raw_text,
                    normalized_text=term.normalized_text,
                    concept_id=result.concept.id,
                    match_method=result.method,
                    confidence_score=result.confidence,
                    rank=rank,
                    review_status="approved" if should_auto_approve else "pending",
                )
                candidates_created += 1
                if should_auto_approve:
                    self.repository.approve_candidate(candidate, "automatic", None)
                    auto_approved += 1
        self.db.commit()
        return TaxonomyLinkRunResult(
            terms_processed=len(terms),
            candidates_created=candidates_created,
            links_auto_approved=auto_approved,
        )

    def link_document_if_taxonomy_available(
        self, term_source: str, document_id: UUID
    ) -> TaxonomyLinkRunResult | None:
        if not self.repository.active_concepts():
            return None
        return self.link_document(term_source, document_id)

    def pending_links(self) -> list[TaxonomyLinkCandidateRead]:
        return [self._candidate_read(item) for item in self.repository.pending_link_candidates()]

    def review_link(
        self,
        candidate_id: UUID,
        review_status: str,
        concept_id: UUID | None,
        user: User,
        replace_selection: bool = False,
        expected_selection_token: str | None = None,
    ) -> TaxonomyLinkCandidateRead:
        try:
            candidate = self.repository.get_link_candidate(candidate_id)
            if not candidate:
                raise HTTPException(status_code=404, detail="Taxonomy link candidate not found.")
            self.repository.lock_term(candidate.term_source, candidate.extracted_term_id)
            candidate = self.repository.get_link_candidate(candidate_id)
            if not candidate:
                raise HTTPException(status_code=409, detail="Suggestions changed. Refresh the review list.")
            if review_status not in {"approved", "rejected"}:
                raise HTTPException(status_code=400, detail="Invalid review status.")
            selected = self.repository.selected_link(candidate.term_source, candidate.extracted_term_id)
            token = self._selection_token(selected)
            if expected_selection_token is not None and expected_selection_token != token:
                raise HTTPException(status_code=409, detail="Selection changed. Refresh before reviewing.")
            target_concept = concept_id or candidate.concept_id
            replacing = selected and (selected.link_candidate_id != candidate.id or selected.concept_id != target_concept)
            if review_status == "approved" and replacing and (not replace_selection or expected_selection_token != token):
                raise HTTPException(status_code=409, detail="A selection already exists. Explicitly confirm its replacement.")
            before = self._review_snapshot(candidate.term_source, candidate.extracted_term_id)
            if target_concept != candidate.concept_id:
                if review_status != "approved":
                    raise HTTPException(status_code=400, detail="Concept correction requires approval.")
                concept = self.repository.get_concept(target_concept)
                if not concept:
                    raise HTTPException(status_code=404, detail="Replacement taxonomy concept not found.")
                if any(item.concept_id == target_concept for item in self.repository.term_candidates(
                        candidate.term_source, candidate.extracted_term_id)):
                    raise HTTPException(status_code=409, detail="That concept is already an alternative. Select that suggestion.")
                candidate.concept_id = concept.id
                candidate.concept = concept
                candidate.match_method = "human_correction"
                candidate.confidence_score = 1.0
            if review_status == "approved":
                self.repository.approve_candidate(candidate, "human_review", user.id)
            else:
                self.repository.reject_candidate(candidate, user.id)
            after = self._review_snapshot(candidate.term_source, candidate.extracted_term_id)
            if before != after:
                action = "replaced" if review_status == "approved" and replacing else review_status
                self.repository.record_review(candidate, action, user.id, before, after)
            self.db.commit()
            return self._candidate_read(self.repository.get_link_candidate(candidate.id))
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _selection_token(selected) -> str | None:
        if not selected:
            return None
        value = f"{selected.id}:{selected.link_candidate_id}:{selected.concept_id}:{selected.approved_at.isoformat()}"
        return sha256(value.encode()).hexdigest()

    def _review_snapshot(self, term_source: str, term_id: UUID) -> dict:
        selected = self.repository.selected_link(term_source, term_id)
        return {
            "selection": None if not selected else {
                "candidate_id": str(selected.link_candidate_id) if selected.link_candidate_id else None,
                "concept_id": str(selected.concept_id), "label": selected.concept.preferred_label,
                "approved_by": str(selected.approved_by) if selected.approved_by else None,
                "approved_at": selected.approved_at.isoformat(), "source": selected.approval_source,
            },
            "candidates": [{"id": str(item.id), "concept_id": str(item.concept_id),
                "label": item.concept.preferred_label, "status": item.review_status,
                "reviewed_by": str(item.reviewed_by) if item.reviewed_by else None,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
                "match_method": item.match_method, "confidence": item.confidence_score}
                for item in self.repository.term_candidates(term_source, term_id)],
        }

    def review_groups(self, state: str, query: str, limit: int, offset: int) -> TaxonomyReviewPage:
        terms = self.repository.review_terms(state, query.strip(), limit + 1, offset)
        groups = []
        for term_source, term_id in terms[:limit]:
            candidates = self.repository.term_candidates(term_source, term_id)
            selected = self.repository.selected_link(term_source, term_id)
            approved_ids = {item.id for item in candidates if item.review_status == "approved"}
            expected_ids = {selected.link_candidate_id} if selected else set()
            groups.append(TaxonomyReviewGroup(term_source=term_source, extracted_term_id=term_id,
                raw_text=candidates[0].raw_text, inconsistent=approved_ids != expected_ids,
                selection=TaxonomySelectionRead(candidate_id=selected.link_candidate_id,
                    concept=self._concept_read(selected.concept), token=self._selection_token(selected)) if selected else None,
                candidates=[self._candidate_read(item) for item in candidates]))
        return TaxonomyReviewPage(items=groups, has_more=len(terms) > limit)

    def review_history(self, term_source: str, term_id: UUID, limit: int, offset: int) -> list[TaxonomyReviewEventRead]:
        return [TaxonomyReviewEventRead.model_validate(item)
                for item in self.repository.review_history(term_source, term_id, limit, offset)]

    @staticmethod
    def _concept_read(concept: TaxonomyConcept) -> TaxonomyConceptRead:
        return TaxonomyConceptRead(
            id=concept.id,
            external_id=concept.external_id,
            preferred_label=concept.preferred_label,
            description=concept.description,
            concept_type=concept.concept_type,
            language=concept.language,
            source_code=concept.taxonomy_version.source.code,
            taxonomy_version=concept.taxonomy_version.version,
            alternative_labels=[label.label for label in concept.labels],
        )

    def _candidate_read(self, candidate) -> TaxonomyLinkCandidateRead:
        return TaxonomyLinkCandidateRead(
            id=candidate.id,
            term_source=candidate.term_source,
            extracted_term_id=candidate.extracted_term_id,
            raw_text=candidate.raw_text,
            normalized_text=candidate.normalized_text,
            match_method=candidate.match_method,
            confidence_score=candidate.confidence_score,
            rank=candidate.rank,
            review_status=candidate.review_status,
            concept=self._concept_read(candidate.concept),
        )
