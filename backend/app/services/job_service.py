import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import ExtractedJobTerm, Job, JobSkill
from app.repositories.document_repository import DocumentRepository
from app.schemas.documents import JobCreate, JobUpdate
from app.core.config import settings
from app.nlp.skill_extractor import ESCO_DIGITAL_SCHEME, EscoConceptLabels, EscoVocabulary, ExtractedTerm, SkillExtractor
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.services.section_detection_service import SectionDetectionService, detect_job_segments
from app.services.text_cleaning_service import TextCleaningService
from app.services.taxonomy_service import TaxonomyService


_VOCABULARY_CACHE: dict[tuple, EscoVocabulary] = {}


def load_esco_vocabulary(db: Session) -> EscoVocabulary | None:
    """Filtered ESCO skill/knowledge labels of the active, non-sample ESCO release, cached per release import."""
    repository = TaxonomyRepository(db)
    release = repository.esco_vocabulary_release()
    if release is None:
        return None
    key = (release.id, release.imported_at)
    if key not in _VOCABULARY_CACHE:
        concepts, labels = repository.esco_vocabulary_rows(release.id)
        labels_by_concept: dict[UUID, list[str]] = defaultdict(list)
        for concept_id, label in labels:
            labels_by_concept[concept_id].append(label)
        items = []
        for concept_id, concept_type, metadata, preferred_label in concepts:
            source = (metadata or {}).get("source", {})
            items.append(
                EscoConceptLabels(
                    concept_type=concept_type,
                    reuse_level=str(source.get("reuseLevel", "")),
                    digital=ESCO_DIGITAL_SCHEME in str(source.get("inScheme", "")),
                    labels=(preferred_label, *labels_by_concept[concept_id]),
                )
            )
        _VOCABULARY_CACHE.clear()
        _VOCABULARY_CACHE[key] = EscoVocabulary.from_concepts(items, f"ESCO-{release.version}")
    return _VOCABULARY_CACHE[key]


def build_job_extractor(
    db: Session, use_esco_vocabulary: bool | None = None, version: str | None = None
) -> SkillExtractor:
    """Job extractor; vocabulary and rule version follow JOB_EXTRACTION_ESCO_VOCABULARY and
    JOB_EXTRACTION_VERSION unless overridden."""
    enabled = settings.JOB_EXTRACTION_ESCO_VOCABULARY if use_esco_vocabulary is None else use_esco_vocabulary
    return SkillExtractor(esco_vocabulary=load_esco_vocabulary(db) if enabled else None,
                          job_version=version or settings.JOB_EXTRACTION_VERSION)


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)
        self.cleaner = TextCleaningService()
        self.section_detector = SectionDetectionService()
        self._skill_extractor: SkillExtractor | None = None

    @property
    def skill_extractor(self) -> SkillExtractor:
        if self._skill_extractor is None:
            self._skill_extractor = build_job_extractor(self.db)
        return self._skill_extractor

    def create_job(self, payload: JobCreate) -> Job:
        cleaned_description = self.cleaner.clean(payload.description)
        job = self.repository.create_job(
            title=payload.title,
            company=payload.company,
            location=payload.location,
            employment_type=payload.employment_type,
            description=payload.description,
            cleaned_description=cleaned_description,
        )
        self._process_existing_job(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self, include_archived: bool = False, exclude_sources=frozenset()) -> list[Job]:
        return [job for job in self.repository.list_jobs(include_archived=include_archived)
                if job.source not in exclude_sources]

    def get_job(self, job_id: UUID, exclude_sources=frozenset()) -> Job:
        job = self.repository.get_job(job_id)
        if not job or job.source in exclude_sources:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job

    def update_job(self, job_id: UUID, payload: JobUpdate) -> Job:
        job = self.get_job(job_id)
        cleaned_description = self.cleaner.clean(payload.description)
        job = self.repository.update_job(
            job=job,
            title=payload.title,
            company=payload.company,
            location=payload.location,
            employment_type=payload.employment_type,
            description=payload.description,
            cleaned_description=cleaned_description,
            status=payload.status,
        )
        self._process_existing_job(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def delete_job(self, job_id: UUID) -> None:
        job = self.get_job(job_id)
        self.repository.delete_job(job)
        self.repository.add_processing_log("job", job_id, "deletion", "success", "Job deleted.")
        self.db.commit()

    def archive_job(self, job_id: UUID) -> Job:
        job = self.get_job(job_id)
        job.status = "archived"
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_job(job.id)
        self.repository.add_processing_log("job", job.id, "archive", "success", "Job archived.")
        self.db.commit()
        self.db.refresh(job)
        return job

    def process_job(self, job_id: UUID) -> Job:
        job = self.get_job(job_id)
        job.cleaned_description = self.cleaner.clean(job.description)
        self._process_existing_job(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def _process_existing_job(self, job: Job) -> None:
        from app.job_sources import EVALUATION_SOURCE

        if job.source == EVALUATION_SOURCE and job.processed_at is not None:
            # The offline evaluation depends on the stored skills of these jobs.
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Evaluation jobs are never re-processed.")
        # Stored sections (display, retrieval input) keep the shared detector; extraction
        # uses the job requirement segmentation, which also drops benefits/EEO/application text.
        sections = self.section_detector.detect(job.cleaned_description)
        self.repository.replace_job_sections(job, sections)
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_job(job.id)
        # Additive like `reextract`: reviews, links and vanished evidence are kept;
        # occurrences moved by an edit keep their review with updated offsets.
        reconciler = JobReextractionService(self.db, extractor=self.skill_extractor)
        plan = reconciler.plan(job, allow_moves=True)
        reconciler.apply(job, plan)
        terms = plan.new_terms
        job.status = "processed"
        job.error_message = ""
        job.processed_at = datetime.now(timezone.utc)
        self.repository.add_processing_log(
            "job",
            job.id,
            "document_processing",
            "success",
            f"Detected {len(sections)} job sections and {len(terms)} new extracted terms.",
            {"section_count": len(sections), "term_count": len(terms), "matched": plan.matched,
             "moved": len(plan.moved), "vanished_kept": len(plan.vanished)},
        )


# ---- Additive re-extraction of existing jobs ----------------------------

@dataclass
class JobReextractionPlan:
    """Difference between a job's stored extraction and a fresh one.

    Occurrences match on (normalized text, type, start, end). Matched items keep
    their review status and links. A pending skill takes a new requirement type;
    an approved one only from unknown to required/preferred; other differences
    on reviewed skills are reported. With `allow_moves` (job edits), a stored
    occurrence with the same text, type and evidence sentence at a different
    span is "moved": it keeps its review and gets the new offsets. A fresh term on the exact span
    of a stored occurrence whose text or type was edited (by a reviewer) is
    paired with it and not added. Remaining stored occurrences are kept and
    reported as vanished.
    """

    job_id: UUID
    title: str
    company: str
    matched: int = 0
    new_terms: list[ExtractedTerm] = field(default_factory=list)
    pending_type_changes: list[tuple[ExtractedJobTerm, JobSkill, str]] = field(default_factory=list)
    approved_upgrades: list[tuple[ExtractedJobTerm, JobSkill, str]] = field(default_factory=list)
    reviewed_type_changes: list[tuple[ExtractedJobTerm, JobSkill, str]] = field(default_factory=list)
    moved: list[tuple[ExtractedJobTerm, JobSkill | None, ExtractedTerm]] = field(default_factory=list)
    reviewer_edited: list[tuple[ExtractedJobTerm, JobSkill | None, ExtractedTerm]] = field(default_factory=list)
    vanished: list[tuple[ExtractedJobTerm, JobSkill | None]] = field(default_factory=list)

    @property
    def changes_data(self) -> bool:
        return bool(self.new_terms or self.pending_type_changes or self.approved_upgrades or self.moved)


def _occurrence_key(normalized_text: str, term_type: str, start: int, end: int) -> tuple:
    return normalized_text, term_type, start, end


def plan_job_reextraction(
    job: Job,
    stored: list[tuple[ExtractedJobTerm, JobSkill | None]],
    extracted: list[ExtractedTerm],
    allow_moves: bool = False,
) -> JobReextractionPlan:
    plan = JobReextractionPlan(job_id=job.id, title=job.title, company=job.company)
    available: dict[tuple, list[tuple[ExtractedJobTerm, JobSkill | None]]] = defaultdict(list)
    for term, skill in stored:
        available[_occurrence_key(term.normalized_text, term.term_type, term.start_char, term.end_char)].append((term, skill))
    matched_ids: set[UUID] = set()
    unmatched: list[ExtractedTerm] = []
    for term in extracted:
        bucket = available.get(_occurrence_key(term.normalized_text, term.term_type, term.start_char, term.end_char))
        if not bucket:
            unmatched.append(term)
            continue
        stored_term, skill = bucket.pop(0)
        matched_ids.add(stored_term.id)
        plan.matched += 1
        _classify_type_change(plan, stored_term, skill, term.requirement_type)
    if allow_moves:
        by_evidence: dict[tuple, list[tuple[ExtractedJobTerm, JobSkill | None]]] = defaultdict(list)
        for term, skill in stored:
            if term.id not in matched_ids:
                by_evidence[(term.normalized_text, term.term_type, term.evidence_sentence)].append((term, skill))
        still_unmatched = []
        for term in unmatched:
            bucket = by_evidence.get((term.normalized_text, term.term_type, term.evidence_sentence))
            if bucket:
                stored_term, skill = bucket.pop(0)
                matched_ids.add(stored_term.id)
                plan.moved.append((stored_term, skill, term))
                _classify_type_change(plan, stored_term, skill, term.requirement_type)
            else:
                still_unmatched.append(term)
        unmatched = still_unmatched
    by_span: dict[tuple[int, int], list[tuple[ExtractedJobTerm, JobSkill | None]]] = defaultdict(list)
    for term, skill in stored:
        if term.id not in matched_ids:
            by_span[(term.start_char, term.end_char)].append((term, skill))
    for term in unmatched:
        edited = by_span.get((term.start_char, term.end_char))
        if edited:
            stored_term, skill = edited.pop(0)
            matched_ids.add(stored_term.id)
            plan.reviewer_edited.append((stored_term, skill, term))
        else:
            plan.new_terms.append(term)
    plan.vanished = [(term, skill) for term, skill in stored if term.id not in matched_ids]
    return plan


def _classify_type_change(plan: JobReextractionPlan, stored_term: ExtractedJobTerm, skill: JobSkill | None, new_type: str) -> None:
    if skill is None or skill.requirement_type == new_type:
        return
    if skill.review_status == "pending":
        plan.pending_type_changes.append((stored_term, skill, new_type))
    elif skill.review_status == "approved" and skill.requirement_type == "unknown" and new_type in {"required", "preferred"}:
        plan.approved_upgrades.append((stored_term, skill, new_type))
    else:
        plan.reviewed_type_changes.append((stored_term, skill, new_type))


class JobReextractionService:
    def __init__(
        self, db: Session, use_esco_vocabulary: bool | None = None, extractor: SkillExtractor | None = None,
        version: str | None = None,
    ) -> None:
        self.db = db
        self.repository = DocumentRepository(db)
        self.extractor = extractor or build_job_extractor(db, use_esco_vocabulary, version)

    def plan(self, job: Job, allow_moves: bool = False) -> JobReextractionPlan:
        """Read-only: extract from the stored cleaned text and compare."""
        text = job.cleaned_description
        terms = self.extractor.extract_from_sections(
            detect_job_segments(text, self.extractor.job_version), text, "job")
        return plan_job_reextraction(job, self.repository.job_extraction_state(job.id), terms, allow_moves)

    def apply(self, job: Job, plan: JobReextractionPlan) -> list[UUID]:
        """Add new terms as pending and retype pending skills; nothing is deleted or re-reviewed."""
        if not plan.changes_data:
            return []
        # Requirement type only; review status, edits and links stay as reviewed.
        for stored_term, skill, requirement_type in [*plan.pending_type_changes, *plan.approved_upgrades]:
            stored_term.requirement_type = requirement_type
            skill.requirement_type = requirement_type
        for stored_term, _, fresh in plan.moved:
            stored_term.start_char, stored_term.end_char = fresh.start_char, fresh.end_char
            stored_term.source_section = fresh.source_section
        new_ids = self.repository.add_job_terms(job, plan.new_terms)
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_job(job.id)
        self.repository.add_processing_log(
            "job", job.id, "additive_reextraction", "success",
            f"Added {len(new_ids)} pending terms; retyped {len(plan.pending_type_changes)} pending and "
            f"{len(plan.approved_upgrades)} approved (unknown) skills.",
            {"new_terms": len(new_ids), "pending_type_changes": len(plan.pending_type_changes),
             "approved_unknown_upgrades": len(plan.approved_upgrades), "moved": len(plan.moved),
             "reviewed_type_changes_reported": len(plan.reviewed_type_changes),
             "vanished_kept": len(plan.vanished), "reviewer_edited_kept": len(plan.reviewer_edited),
             "matched": plan.matched,
             "extraction_methods": sorted({term.extraction_method for term in plan.new_terms})},
        )
        self.db.commit()
        if new_ids:
            TaxonomyService(self.db).link_document_if_taxonomy_available("job", job.id, term_ids=set(new_ids))
        return new_ids


def retirable(db: Session, job: Job, plan: JobReextractionPlan) -> list[tuple[ExtractedJobTerm, JobSkill | None]]:
    """Vanished items of a live job that no person has touched.

    An item qualifies when its job skill is still pending with the extracted text and
    type, the term itself is pending, and no person reviewed or approved a taxonomy link
    for it (only automatic link approvals). Evaluation and manual jobs never qualify.
    """
    from sqlalchemy import select
    from app.db.models import ApprovedTaxonomyLink, TaxonomyLinkCandidate
    from app.db.models.taxonomy import TaxonomyReviewEvent
    from app.job_sources import NON_LIVE_SOURCES

    if job.source is None or job.source in NON_LIVE_SOURCES or not plan.vanished:
        return []
    term_ids = [term.id for term, _ in plan.vanished]
    touched = set(db.scalars(select(TaxonomyReviewEvent.extracted_term_id).where(
        TaxonomyReviewEvent.term_source == "job", TaxonomyReviewEvent.extracted_term_id.in_(term_ids))))
    touched |= set(db.scalars(select(ApprovedTaxonomyLink.extracted_term_id).where(
        ApprovedTaxonomyLink.term_source == "job", ApprovedTaxonomyLink.extracted_term_id.in_(term_ids),
        ApprovedTaxonomyLink.approval_source != "automatic")))
    touched |= set(db.scalars(select(TaxonomyLinkCandidate.extracted_term_id).where(
        TaxonomyLinkCandidate.term_source == "job", TaxonomyLinkCandidate.extracted_term_id.in_(term_ids),
        TaxonomyLinkCandidate.reviewed_by.is_not(None))))
    return [
        (term, skill) for term, skill in plan.vanished
        if term.id not in touched and term.review_status == "pending"
        and (skill is None or (skill.review_status == "pending" and skill.normalized_text == term.normalized_text
                               and skill.skill_type == term.term_type))
    ]


def retire(db: Session, job: Job, items: list[tuple[ExtractedJobTerm, JobSkill | None]]) -> int:
    """Delete untouched vanished items with their automatic links; logged on the job."""
    if not items:
        return 0
    repository = DocumentRepository(db)
    repository._delete_taxonomy_links("job", [term.id for term, _ in items])
    for term, skill in items:
        if skill is not None:
            db.delete(skill)
        db.delete(term)
    from app.repositories.retrieval_repository import RetrievalRepository
    RetrievalRepository(db).invalidate_job(job.id)
    repository.add_processing_log(
        "job", job.id, "retire_unreviewed", "success",
        f"Removed {len(items)} unreviewed terms the current extraction no longer finds.",
        {"retired": len(items), "extraction_methods": sorted({term.extraction_method for term, _ in items})},
    )
    db.commit()
    return len(items)


def _requirement_counts(items) -> str:
    counts = Counter(items)
    return "/".join(str(counts.get(kind, 0)) for kind in ("required", "preferred", "unknown"))


def _print_plan(plan: JobReextractionPlan, verbose: bool) -> None:
    esco = sum(term.extraction_method.startswith("esco_vocabulary") for term in plan.new_terms)
    vanished_reviewed = sum(1 for _, skill in plan.vanished if skill is not None and skill.review_status != "pending")
    print(
        f"{str(plan.job_id)[:8]}  {plan.title[:38]:<38} {plan.company[:16]:<16} "
        f"matched {plan.matched:>3} | new {len(plan.new_terms):>3} (r/p/u {_requirement_counts(t.requirement_type for t in plan.new_terms)}, "
        f"esco {esco}) | retype pending {len(plan.pending_type_changes):>2} | approved unknown->typed {len(plan.approved_upgrades):>2} | reviewed differs {len(plan.reviewed_type_changes):>2} "
        f"| edited kept {len(plan.reviewer_edited):>2} | vanished {len(plan.vanished):>2} (reviewed {vanished_reviewed})"
    )
    if not verbose:
        return
    for term in plan.new_terms:
        print(f"    + {term.normalized_text!r} [{term.term_type}] {term.requirement_type} in {term.source_section} ({term.extraction_method})")
    for _, skill, new_type in plan.pending_type_changes:
        print(f"    ~ {skill.normalized_text!r} pending: {skill.requirement_type} -> {new_type}")
    for _, skill, new_type in plan.approved_upgrades:
        print(f"    ^ {skill.normalized_text!r} approved: unknown -> {new_type} (review kept)")
    for _, skill, new_type in plan.reviewed_type_changes:
        print(f"    ! {skill.normalized_text!r} {skill.review_status}: stays {skill.requirement_type}, extraction says {new_type}")
    for stored_term, skill, term in plan.reviewer_edited:
        print(f"    = {stored_term.normalized_text!r} {skill.review_status if skill else 'no skill'}: kept; not adding {term.normalized_text!r}")
    for term, skill in plan.vanished:
        print(f"    - {term.normalized_text!r} [{term.term_type}] {skill.review_status if skill else 'no skill'}: kept")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Additively re-extract existing jobs (dry-run unless --apply).")
    subcommands = parser.add_subparsers(dest="command", required=True)
    reextract = subcommands.add_parser("reextract")
    reextract.add_argument("--apply", action="store_true", help="write changes; default is a read-only dry-run")
    reextract.add_argument("--esco", choices=["config", "on", "off"], default="config",
                           help="ESCO vocabulary; default follows JOB_EXTRACTION_ESCO_VOCABULARY")
    reextract.add_argument("--version", choices=["config", "v3", "v4"], default="config",
                           help="rule version; default follows JOB_EXTRACTION_VERSION")
    reextract.add_argument("--sources", choices=["live", "all"], default="live",
                           help="live job sources only (default), or also manually added jobs")
    reextract.add_argument("--retire-unreviewed", action="store_true",
                           help="with --apply: remove vanished items of live jobs that no person has touched")
    reextract.add_argument("--job", action="append", default=[], help="job UUID (repeatable); default all active jobs")
    reextract.add_argument("--include-archived", action="store_true")
    reextract.add_argument("--verbose", action="store_true", help="list every term per job")
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal

    from app.job_sources import EVALUATION_SOURCE, NON_LIVE_SOURCES

    esco = {"config": None, "on": True, "off": False}[args.esco]
    with SessionLocal() as db:
        service = JobReextractionService(db, use_esco_vocabulary=esco,
                                         version=None if args.version == "config" else args.version)
        repository = DocumentRepository(db)
        jobs = [repository.get_job(UUID(value)) for value in args.job] if args.job else repository.list_jobs(
            include_archived=args.include_archived)
        # The evaluation jobs are never re-extracted: the offline evaluation depends on their stored skills.
        skipped = [job for job in jobs if job is not None and (job.source == EVALUATION_SOURCE or (
            args.sources == "live" and job.source in NON_LIVE_SOURCES))]
        jobs = sorted((job for job in jobs if job is not None and job not in skipped),
                      key=lambda job: (job.title.casefold(), str(job.id)))
        vocabulary = service.extractor.esco_vocabulary
        print(f"{'APPLY' if args.apply else 'DRY-RUN (no writes)'}: {len(jobs)} jobs ({len(skipped)} evaluation/"
              f"non-live skipped), extraction contract {service.extractor.job_version}, "
              f"ESCO vocabulary {vocabulary.version + ' (o7)' if vocabulary else 'off'}")
        totals: Counter = Counter()
        changed: list[UUID] = []
        for job in jobs:
            plan = service.plan(job)
            _print_plan(plan, args.verbose)
            retirable_items = retirable(db, job, plan) if args.retire_unreviewed else []
            totals.update(retirable=len(retirable_items))
            totals.update(matched=plan.matched, new=len(plan.new_terms), retype_pending=len(plan.pending_type_changes),
                          reviewed_differs=len(plan.reviewed_type_changes), vanished=len(plan.vanished),
                          reviewer_edited=len(plan.reviewer_edited), approved_upgrades=len(plan.approved_upgrades),
                          new_esco=sum(t.extraction_method.startswith("esco_vocabulary") for t in plan.new_terms))
            if plan.changes_data or retirable_items:
                changed.append(job.id)
                if args.apply:
                    service.apply(job, plan)
                    retire(db, job, retirable_items)
        if not args.apply:
            db.rollback()
        print(f"TOTAL {dict(totals)}; jobs with changes: {len(changed)}")
        if args.apply and changed:
            # The index command re-embeds only jobs whose embedding input (source hash) changed.
            print("Changed jobs: " + ", ".join(map(str, changed)))
            print("Reindex them with: python -m app.retrieval.cli index jobs --limit 100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
