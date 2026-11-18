"""Transitional skill-coverage matching (Phase 6 prototype; see DECISIONS.md D036, D044).

Retrieval ranks, coverage explains (D044): jobs are ordered by Phase 5
retrieval similarity, and skill coverage is reported per job as counts, never
as a weighted score. The former lexicographic coverage order is kept as
`coverage_ranking_key` for the offline comparison (D043).
"""
from dataclasses import dataclass, field
from fractions import Fraction
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import CandidateJobMatch, Job, User
from app.repositories.document_repository import DocumentRepository

# Types compared as skills. Every other approved job term type (qualification,
# experience_indicator, certification, occupation, ...) is listed as
# "not assessed by the system" and never scored.
SKILL_LIKE_TYPES = frozenset({"skill", "tool", "domain_knowledge", "language"})
MATCHED_VIA_CONCEPT = "taxonomy_concept"
MATCHED_VIA_NAME = "skill_name"
# How a missing job skill was looked for: by taxonomy concept (and name), or by name only.
CHECKED_VIA_CONCEPT = "taxonomy_concept"
CHECKED_VIA_NAME = "skill_name"


@dataclass(frozen=True)
class SkillItem:
    name: str
    skill_type: str
    concept_id: UUID | None = None
    concept_label: str | None = None
    requirement: str = ""


@dataclass
class CoverageResult:
    matched_required: list[dict] = field(default_factory=list)
    matched_preferred: list[dict] = field(default_factory=list)
    missing_required: list[dict] = field(default_factory=list)
    missing_preferred: list[dict] = field(default_factory=list)
    not_assessed_required: list[str] = field(default_factory=list)
    not_assessed_preferred: list[str] = field(default_factory=list)
    candidate_skill_count: int = 0

    @property
    def required_total(self) -> int:
        return len(self.matched_required) + len(self.missing_required)

    @property
    def preferred_total(self) -> int:
        return len(self.matched_preferred) + len(self.missing_preferred)


@dataclass
class _JobGroup:
    label: str
    concept_id: UUID | None
    names: set[str]
    required: bool


def _sorted_labels(values) -> list[str]:
    return sorted(set(values), key=lambda value: (value.casefold(), value))


def _job_groups(job_items: list[SkillItem]) -> list[_JobGroup]:
    """Deduplicate job skills: by concept when linked, otherwise by name.

    An unlinked occurrence whose name equals a linked occurrence joins that
    concept group. `unknown` requirements count as preferred; when the same
    skill is listed both ways, required wins.
    """
    by_concept: dict[UUID, _JobGroup] = {}
    for item in job_items:
        if item.concept_id is None:
            continue
        group = by_concept.setdefault(
            item.concept_id, _JobGroup(item.concept_label or item.name, item.concept_id, set(), False)
        )
        group.names.add(item.name)
        group.required |= item.requirement == "required"
    by_name: dict[str, _JobGroup] = {}
    for item in job_items:
        if item.concept_id is not None:
            continue
        group = next((g for g in by_concept.values() if item.name in g.names), None)
        if group is None:
            group = by_name.setdefault(item.name, _JobGroup(item.name, None, {item.name}, False))
        group.required |= item.requirement == "required"
    return [*by_concept.values(), *by_name.values()]


def compute_coverage(candidate_items: list[SkillItem], job_items: list[SkillItem]) -> CoverageResult:
    """Compare approved candidate and job skills.

    Two skills match by taxonomy concept when both carry an approved link;
    otherwise they match by identical normalized name. Every compared job skill
    is either matched or missing. A missing skill records whether it was looked
    for by concept or by name only; a name-only miss may still be in the CV
    under different wording.
    """
    candidate = [item for item in candidate_items if item.skill_type in SKILL_LIKE_TYPES]
    candidate_concepts = {item.concept_id for item in candidate if item.concept_id is not None}
    unlinked_candidate_names = {item.name for item in candidate if item.concept_id is None}
    all_candidate_names = {item.name for item in candidate}

    result = CoverageResult(candidate_skill_count=len(candidate))
    for group in _job_groups([item for item in job_items if item.skill_type in SKILL_LIKE_TYPES]):
        if group.concept_id is not None:
            checked_via = CHECKED_VIA_CONCEPT
            if group.concept_id in candidate_concepts:
                via = MATCHED_VIA_CONCEPT
            elif group.names & unlinked_candidate_names:
                via = MATCHED_VIA_NAME
            else:
                via = None
        else:
            checked_via = CHECKED_VIA_NAME
            via = MATCHED_VIA_NAME if group.names & all_candidate_names else None
        if via is not None:
            target = result.matched_required if group.required else result.matched_preferred
            target.append({"label": group.label, "matched_via": via})
        else:
            target = result.missing_required if group.required else result.missing_preferred
            target.append({"label": group.label, "checked_via": checked_via})

    def by_label(entry: dict) -> tuple[str, str]:
        return entry["label"].casefold(), entry["label"]

    for entries in (result.matched_required, result.matched_preferred,
                    result.missing_required, result.missing_preferred):
        entries.sort(key=by_label)
    other = [item for item in job_items if item.skill_type not in SKILL_LIKE_TYPES]
    result.not_assessed_required = _sorted_labels(i.name for i in other if i.requirement == "required")
    result.not_assessed_preferred = _sorted_labels(
        i.name for i in other if i.requirement != "required" and i.name not in result.not_assessed_required
    )
    return result


def _coverage_line(kind: str, matched: list[dict], missing: list[dict]) -> str:
    total = len(matched) + len(missing)
    if total == 0:
        return f"This job lists no comparable {kind} skills."
    line = f"{kind.capitalize()} skills: {len(matched)} of {total} matched"
    if matched:
        line += " (" + ", ".join(entry["label"] for entry in matched) + ")"
    if missing:
        line += "; missing: " + ", ".join(entry["label"] for entry in missing)
    return line + "."


def build_explanation(result: CoverageResult) -> str:
    """Describe coverage using only the stored matched/missing/not-assessed lists."""
    lines = [
        _coverage_line("required", result.matched_required, result.missing_required),
        _coverage_line("preferred", result.matched_preferred, result.missing_preferred),
    ]
    by_name = [entry["label"] for entry in result.missing_required + result.missing_preferred
               if entry["checked_via"] == CHECKED_VIA_NAME]
    if by_name:
        lines.append("Checked by name only (may appear in your CV under a different wording): "
                     + ", ".join(by_name) + ".")
    if result.not_assessed_required:
        lines.append("Also required — not assessed by the system: " + ", ".join(result.not_assessed_required) + ".")
    if result.not_assessed_preferred:
        lines.append("Also preferred — not assessed by the system: " + ", ".join(result.not_assessed_preferred) + ".")
    return "\n".join(lines)


def ranking_key(match: CandidateJobMatch, similarity: float | None) -> tuple:
    """App order (D044): retrieval similarity, highest first, then job ID.

    Jobs without a fresh similarity (job or profile not indexed, or stale) go
    last. Coverage does not affect the order; it explains each job.
    """
    return (similarity is None, -(similarity or 0.0), str(match.job_id))


def coverage_ranking_key(match: CandidateJobMatch, similarity: float | None) -> tuple:
    """Former app order, kept for the offline comparison (D043, variants B-D).

    Lexicographic (D040): required coverage, preferred coverage,
    matched required count, matched preferred count, retrieval similarity, job ID.

    Jobs without required skills sort last; within equal required coverage,
    jobs without preferred skills sort after those with some. When both
    fractions tie, more matched skills rank first (2 of 2 before 1 of 1).
    Missing similarity (job or profile not indexed) sorts after present.
    """
    required_total = len(match.matched_required) + len(match.missing_required)
    preferred_total = len(match.matched_preferred) + len(match.missing_preferred)
    required = Fraction(len(match.matched_required), required_total) if required_total else Fraction(0)
    preferred = Fraction(len(match.matched_preferred), preferred_total) if preferred_total else Fraction(0)
    return (
        required_total == 0, -required,
        preferred_total == 0, -preferred,
        -len(match.matched_required), -len(match.matched_preferred),
        similarity is None, -(similarity or 0.0),
        str(match.job_id),
    )


class MatchingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)

    def refresh_my_recommendations(self, user: User) -> list[CandidateJobMatch]:
        matches = self._recompute(user)
        self.repository.add_processing_log(
            "candidate_profile",
            self.repository.get_or_create_candidate_profile(user.id).id,
            "job_matching",
            "success",
            f"Refreshed skill coverage for {len(matches)} jobs.",
            {"job_count": len(matches)},
        )
        self.db.commit()
        return matches

    def list_my_recommendations(self, user: User) -> list[CandidateJobMatch]:
        # Always recomputed so stored rows never reflect an older rule or stale reviews.
        matches = self._recompute(user)
        self.db.commit()
        return matches

    def match_my_job(self, user: User, job_id: UUID) -> CandidateJobMatch:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        job = self.repository.get_job(job_id)
        if not job or job.status == "archived":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        match = self._score_job(profile.id, job, self._candidate_items(profile.id))
        self.repository.add_processing_log(
            "job",
            job.id,
            "job_matching",
            "success",
            f"Calculated skill coverage for {job.title}.",
            {"required_matched": len(match.matched_required),
             "required_total": len(match.matched_required) + len(match.missing_required)},
        )
        self.db.commit()
        self.db.refresh(match)
        return match

    def _recompute(self, user: User) -> list[CandidateJobMatch]:
        profile = self.repository.get_or_create_candidate_profile(user.id)
        jobs = self.repository.list_jobs(include_archived=False)
        candidate_items = self._candidate_items(profile.id)
        matches = [self._score_job(profile.id, job, candidate_items) for job in jobs]
        similarities = self._retrieval_similarities(user, len(jobs)) if matches else {}
        return sorted(matches, key=lambda match: ranking_key(match, similarities.get(match.job_id)))

    def _retrieval_similarities(self, user: User, job_count: int) -> dict[UUID, float]:
        """Similarity orders the jobs (D044); unavailable or stale indexes simply omit it."""
        from app.services.retrieval_service import RetrievalService

        try:
            rows = RetrievalService(self.db).jobs_for_user(user, job_count)
        except (HTTPException, RuntimeError, ValueError):
            return {}
        return {row["job_id"]: row["retrieval_similarity"] for row in rows}

    def _candidate_items(self, candidate_profile_id: UUID) -> list[SkillItem]:
        skills = self.repository.list_matchable_candidate_skills(candidate_profile_id)
        concepts = self.repository.approved_skill_concepts("candidate", skills)
        return [self._item(skill, concepts.get(skill.id), "") for skill in skills]

    def _job_items(self, job_id: UUID) -> list[SkillItem]:
        skills = self.repository.list_matchable_job_skills(job_id)
        concepts = self.repository.approved_skill_concepts("job", skills)
        return [self._item(skill, concepts.get(skill.id), skill.requirement_type) for skill in skills]

    @staticmethod
    def _item(skill, concept: tuple[UUID, str] | None, requirement: str) -> SkillItem:
        return SkillItem(
            name=skill.normalized_text,
            skill_type=skill.skill_type,
            concept_id=concept[0] if concept else None,
            concept_label=concept[1] if concept else None,
            requirement=requirement,
        )

    def _score_job(self, candidate_profile_id: UUID, job: Job, candidate_items: list[SkillItem]) -> CandidateJobMatch:
        result = compute_coverage(candidate_items, self._job_items(job.id))
        # `score` is a legacy column: required coverage x 100, stored but never displayed or ranked on.
        score = round(100 * len(result.matched_required) / result.required_total, 2) if result.required_total else 0.0
        return self.repository.upsert_candidate_job_match(
            candidate_profile_id=candidate_profile_id,
            job_id=job.id,
            score=score,
            matched_required=result.matched_required,
            matched_preferred=result.matched_preferred,
            missing_required=result.missing_required,
            missing_preferred=result.missing_preferred,
            candidate_skill_count=result.candidate_skill_count,
            job_skill_count=result.required_total + result.preferred_total,
            explanation=build_explanation(result),
        )
