"""Job recommendations: top-N retrieval, explained by skill coverage (DECISIONS.md D045).

Phase 5 retrieval returns the top-N jobs by similarity; that order is the
ranking. Skill coverage is reported per retrieved job as counts and labels,
never as a weighted score, and never changes the order (D036, D040, D044,
D045). The former lexicographic coverage order is kept as
`coverage_ranking_key` for the offline comparison (D043).
"""
from dataclasses import dataclass, field
from fractions import Fraction
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Job, User
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
# Partial coverage (D050): a missing concept-linked job skill whose direct ESCO broader
# skill/knowledge concept is also a direct broader concept of one of the candidate's skills.
BroaderMap = dict[UUID, dict[UUID, str]]


@dataclass(frozen=True)
class SkillItem:
    name: str
    skill_type: str
    concept_id: UUID | None = None
    concept_label: str | None = None
    requirement: str = ""
    # False for a pending skill on a live job: automatically extracted, not reviewed (D054).
    reviewed: bool = True


@dataclass
class CoverageResult:
    matched_required: list[dict] = field(default_factory=list)
    matched_preferred: list[dict] = field(default_factory=list)
    missing_required: list[dict] = field(default_factory=list)
    missing_preferred: list[dict] = field(default_factory=list)
    partial_required: list[dict] = field(default_factory=list)
    partial_preferred: list[dict] = field(default_factory=list)
    not_assessed_required: list[str] = field(default_factory=list)
    not_assessed_preferred: list[str] = field(default_factory=list)
    candidate_skill_count: int = 0

    @property
    def required_total(self) -> int:
        return len(self.matched_required) + len(self.partial_required) + len(self.missing_required)

    @property
    def preferred_total(self) -> int:
        return len(self.matched_preferred) + len(self.partial_preferred) + len(self.missing_preferred)


@dataclass
class _JobGroup:
    label: str
    concept_id: UUID | None
    names: set[str]
    required: bool
    reviewed: bool = False


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
        group.reviewed |= item.reviewed
    by_name: dict[str, _JobGroup] = {}
    for item in job_items:
        if item.concept_id is not None:
            continue
        group = next((g for g in by_concept.values() if item.name in g.names), None)
        if group is None:
            group = by_name.setdefault(item.name, _JobGroup(item.name, None, {item.name}, False))
        group.required |= item.requirement == "required"
        group.reviewed |= item.reviewed
    return [*by_concept.values(), *by_name.values()]


def compute_coverage(candidate_items: list[SkillItem], job_items: list[SkillItem],
                     broader: BroaderMap | None = None) -> CoverageResult:
    """Compare approved candidate and job skills.

    Two skills match by taxonomy concept when both carry an approved link;
    otherwise they match by identical normalized name. Every compared job skill
    is matched, related (shown as "Related skill in your profile") or missing. A missing skill records whether it
    was looked for by concept or by name only; a name-only miss may still be in
    the CV under different wording.

    With `broader` (D050), a concept-linked job skill that is not matched is
    related when it shares a direct ESCO broader skill/knowledge
    concept with a concept-linked candidate skill. Without it (offline
    comparison, D043) there is no partial class.
    """
    candidate = [item for item in candidate_items if item.skill_type in SKILL_LIKE_TYPES]
    candidate_concepts = {item.concept_id for item in candidate if item.concept_id is not None}
    unlinked_candidate_names = {item.name for item in candidate if item.concept_id is None}
    all_candidate_names = {item.name for item in candidate}
    # Broader concept ID -> (broader label, candidate skill label) for the evidence text.
    candidate_broader: dict[UUID, tuple[str, str]] = {}
    for item in sorted((i for i in candidate if i.concept_id is not None),
                       key=lambda i: ((i.concept_label or i.name).casefold(), str(i.concept_id))):
        for parent_id, parent_label in (broader or {}).get(item.concept_id, {}).items():
            candidate_broader.setdefault(parent_id, (parent_label, item.concept_label or item.name))

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
        shared = sorted(
            (candidate_broader[parent_id] for parent_id in (broader or {}).get(group.concept_id, {})
             if parent_id in candidate_broader),
            key=lambda pair: (pair[0].casefold(), pair[1].casefold()),
        ) if via is None and group.concept_id is not None else []
        # A group is reviewed when any of its occurrences is approved; only then is the flag omitted.
        flag = {} if group.reviewed else {"reviewed": False}
        if via is not None:
            target = result.matched_required if group.required else result.matched_preferred
            target.append({"label": group.label, "matched_via": via, **flag})
        elif shared:
            target = result.partial_required if group.required else result.partial_preferred
            target.append({"label": group.label, "broader_concept": shared[0][0], "candidate_skill": shared[0][1],
                           **flag})
        else:
            target = result.missing_required if group.required else result.missing_preferred
            target.append({"label": group.label, "checked_via": checked_via, **flag})

    def by_label(entry: dict) -> tuple[str, str]:
        return entry["label"].casefold(), entry["label"]

    for entries in (result.matched_required, result.matched_preferred,
                    result.partial_required, result.partial_preferred,
                    result.missing_required, result.missing_preferred):
        entries.sort(key=by_label)
    other = [item for item in job_items if item.skill_type not in SKILL_LIKE_TYPES]
    result.not_assessed_required = _sorted_labels(i.name for i in other if i.requirement == "required")
    result.not_assessed_preferred = _sorted_labels(
        i.name for i in other if i.requirement != "required" and i.name not in result.not_assessed_required
    )
    return result


def _coverage_line(kind: str, matched: list[dict], missing: list[dict], partial: list[dict] = ()) -> str:
    total = len(matched) + len(partial) + len(missing)
    if total == 0:
        return f"This job lists no comparable {kind} skills."
    line = f"{kind.capitalize()} skills: {len(matched)} of {total} matched"
    if matched:
        line += " (" + ", ".join(entry["label"] for entry in matched) + ")"
    if partial:
        line += "; related skill in your profile: " + ", ".join(entry["label"] for entry in partial)
    if missing:
        line += "; missing: " + ", ".join(entry["label"] for entry in missing)
    return line + "."


def build_explanation(result: CoverageResult) -> str:
    """Describe coverage using only the matched/partial/missing/not-assessed lists."""
    lines = [
        _coverage_line("required", result.matched_required, result.missing_required, result.partial_required),
        _coverage_line("preferred", result.matched_preferred, result.missing_preferred, result.partial_preferred),
    ]
    for entry in result.partial_required + result.partial_preferred:
        lines.append(f"{entry['label']}: not in your CV, but related: you have {entry['candidate_skill']} "
                     f"(same ESCO area: {entry['broader_concept']}).")
    unreviewed = [entry["label"] for entry in (result.matched_required + result.matched_preferred
                                               + result.partial_required + result.partial_preferred
                                               + result.missing_required + result.missing_preferred)
                  if entry.get("reviewed") is False]
    if unreviewed:
        lines.append("Automatically extracted, not reviewed: " + ", ".join(unreviewed) + ".")
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


PROFILE_MESSAGES = {
    "ready": "",
    "profile_not_ready": "Add a CV with consent to processing to build your matching profile.",
    "no_approved_skills": "Approve at least one skill on the CVs page. Your matching profile is built "
                          "from approved skills only.",
    "profile_not_indexed": "Your matching profile has no up-to-date embedding, so jobs cannot be retrieved "
                           "yet. It is rebuilt automatically after your skills change; if this message stays, "
                           "the embedding model is unavailable on the server.",
    "retrieval_unavailable": "Job retrieval is unavailable on the server (the pinned embedding model "
                             "or tokenizer is missing). Please contact the administrator.",
}


def coverage_ranking_key(match, similarity: float | None) -> tuple:
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

    def refresh_my_recommendations(self, user: User) -> dict:
        recommendations = self.list_my_recommendations(user)
        self.repository.add_processing_log(
            "candidate_profile",
            self.repository.get_or_create_candidate_profile(user.id).id,
            "job_matching",
            "success",
            f"Refreshed skill coverage for {len(recommendations['results'])} retrieved jobs.",
            {"job_count": len(recommendations["results"]), "status": recommendations["status"]},
        )
        self.db.commit()
        return recommendations

    def list_my_recommendations(self, user: User) -> dict:
        """Top-N retrieval, then skill coverage per retrieved job (D045).

        "#N of M" is the retrieval rank within the M retrieved jobs. Coverage
        never changes the order. Computed on read (D049): nothing is stored per
        request, so results never reflect an older rule or stale reviews.
        """
        from app.core.config import settings
        from app.services.retrieval_service import RetrievalService

        from app.job_sources import candidate_excluded_sources

        top_n = settings.RECOMMENDATION_TOP_N
        excluded = candidate_excluded_sources()
        profile = self.repository.get_or_create_candidate_profile(user.id)
        retrieval = RetrievalService(self.db)
        # Candidate scope (D056): manual and live jobs; evaluation jobs only when enabled.
        active_jobs = [job for job in self.repository.list_jobs(include_archived=False) if job.source not in excluded]
        state, query = retrieval.profile_readiness(user)
        rows: list[dict] = []
        if state == "ready":
            try:
                rows = self._retrieve(retrieval, query, top_n, excluded)
            except (RuntimeError, ValueError):
                # e.g. the pinned tokenizer needed for job freshness is missing on this server.
                state = "retrieval_unavailable"
        jobs = {job.id: job for job in active_jobs}
        candidate_items = self._candidate_items(profile.id)
        results = []
        for row in rows:
            job = jobs.get(row["job_id"])
            if job is None:
                continue
            results.append({"rank": len(results) + 1, **self._coverage(job, candidate_items)})
        # Only a newly created empty profile is written here; no match rows (D049).
        self.db.commit()
        return {"status": state, "message": PROFILE_MESSAGES[state], "top_n": top_n,
                "active_jobs": len(active_jobs),
                "unindexed_jobs": self._unindexed_job_count(retrieval, active_jobs, excluded),
                "results": results}

    @staticmethod
    def _retrieve(retrieval, query, top_n: int, exclude_sources=frozenset()) -> list[dict]:
        return retrieval.retrieve(query, top_n, exclude_sources=exclude_sources)

    @staticmethod
    def _unindexed_job_count(retrieval, active_jobs: list[Job], exclude_sources=frozenset()) -> int:
        try:
            fresh = retrieval.fresh_job_ids(exclude_sources)
        except RuntimeError:
            # Job freshness under template v2 needs the pinned tokenizer; report every job as unknown.
            return len(active_jobs)
        return sum(1 for job in active_jobs if job.id not in fresh)

    def match_my_job(self, user: User, job_id: UUID) -> dict:
        """Coverage of one active job for the candidate, computed on read (D049)."""
        profile = self.repository.get_or_create_candidate_profile(user.id)
        from app.job_sources import candidate_excluded_sources

        job = self.repository.get_job(job_id)
        if not job or job.status == "archived" or job.source in candidate_excluded_sources():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        coverage = self._coverage(job, self._candidate_items(profile.id))
        self.db.commit()
        return coverage

    def _candidate_items(self, candidate_profile_id: UUID) -> list[SkillItem]:
        skills = self.repository.list_matchable_candidate_skills(candidate_profile_id)
        concepts = self.repository.approved_skill_concepts("candidate", skills)
        return [self._item(skill, concepts.get(skill.id), "") for skill in skills]

    def _job_items(self, job_id: UUID, include_unreviewed: bool = False) -> list[SkillItem]:
        """Approved job skills; with `include_unreviewed` (live jobs, D054) also pending ones."""
        skills = self.repository.list_matchable_job_skills(job_id, include_unreviewed)
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
            reviewed=skill.review_status == "approved",
        )

    def _coverage(self, job: Job, candidate_items: list[SkillItem]) -> dict:
        from app.job_sources import NON_LIVE_SOURCES

        # Live jobs are rarely reviewed: their pending skills count, flagged as not reviewed (D054).
        job_items = self._job_items(job.id, include_unreviewed=job.source not in NON_LIVE_SOURCES)
        concepts = {item.concept_id for item in candidate_items + job_items if item.concept_id is not None}
        broader = self.repository.specific_esco_broader_concepts(concepts)
        result = compute_coverage(candidate_items, job_items, broader)
        return {
            "job_id": job.id,
            "job": job,
            "matched_required": result.matched_required,
            "matched_preferred": result.matched_preferred,
            "missing_required": result.missing_required,
            "missing_preferred": result.missing_preferred,
            "partial_required": result.partial_required,
            "partial_preferred": result.partial_preferred,
            "candidate_skill_count": result.candidate_skill_count,
            "job_skill_count": result.required_total + result.preferred_total,
            "explanation": build_explanation(result),
        }
