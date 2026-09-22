from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import TaxonomyConcept, User
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.schemas.taxonomy import (
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
        try:
            parsed = self.parser.parse(filename, content, source_code)
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not parsed.concepts and not parsed.occupations:
            raise HTTPException(status_code=400, detail="The import file contains no usable concepts or occupations.")

        name, homepage, description = SOURCE_DETAILS[source_code]
        source = self.repository.get_or_create_source(source_code, name, homepage, description)
        taxonomy_version = self.repository.replace_version(
            source=source,
            version=version.strip(),
            release_date=release_date.strip(),
            import_filename=filename,
            checksum=self.parser.checksum(content),
            is_sample=is_sample,
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
    ) -> TaxonomyLinkCandidateRead:
        candidate = self.repository.get_link_candidate(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Taxonomy link candidate not found.")
        if concept_id and concept_id != candidate.concept_id:
            concept = self.repository.get_concept(concept_id)
            if not concept:
                raise HTTPException(status_code=404, detail="Replacement taxonomy concept not found.")
            candidate.concept_id = concept.id
            candidate.concept = concept
            candidate.match_method = "human_correction"
            candidate.confidence_score = 1.0
        if review_status == "approved":
            self.repository.approve_candidate(candidate, "human_review", user.id)
        else:
            self.repository.reject_candidate(candidate, user.id)
        self.db.commit()
        return self._candidate_read(self.repository.get_link_candidate(candidate.id))

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
