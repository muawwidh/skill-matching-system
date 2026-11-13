"""Explicit, transactional Phase 6 orchestration. Never indexes or refreshes matches."""
from dataclasses import asdict, is_dataclass
from fractions import Fraction
import hashlib
import json
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User, CandidateProfile
from app.db.models.explainable import (MatchingRun, JobMatchResult, MatchScoreComponent,
    SkillGapResult, SkillGapAtomicResult)
from app.matching.assessment import InputConsistencyError, assess_inputs
from app.matching.policy import (POLICY_VERSION, POLICY_HASH, Component, assess, decimal_value,
    fingerprint, fraction_string, normalize)
from app.repositories.matching_runs_repository import MatchingRunsRepository
from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_V2
from app.services.retrieval_service import RetrievalService


def json_value(value):
    """Bound snapshots contain JSON values, not ORM state or complete source documents."""
    def encode(item):
        if isinstance(item, Fraction):
            return fraction_string(item)
        if is_dataclass(item):
            return asdict(item)
        return str(item)
    return json.loads(json.dumps(value, default=encode))


def exact(value):
    return fraction_string(value) if value is not None else None


def numeric(value):
    return decimal_value(value) if value is not None else None


class SnapshotLimitError(ValueError):
    """Evidence cannot fit safely without losing mandatory reconstruction references."""


def bounded_snapshot(value, limit: int, label: str) -> dict:
    value = json_value(value)
    # Include JSONB's spaces and use UTF-8 bytes, conservatively tighter than its
    # character-count CHECK. This affects stored excerpts only, never assessment.
    if len(json.dumps(value, ensure_ascii=False).encode()) > limit:
        raise SnapshotLimitError(label)
    return value


def reference_summary(rows: list[dict], lookup: str) -> tuple[list[dict], dict]:
    return rows[:8], {"total": len(rows), "omitted_count": max(0, len(rows) - 8),
        "complete_sequence_sha256": fingerprint(rows), "complete_records_in": lookup}


def result_order_key(value: dict) -> tuple:
    score = value["alignment_fraction"]
    return (score is None, -Fraction(score) if score is not None else Fraction(0),
            value["original_retrieval_rank"], str(value["job_id"] or "").lower())


class MatchingRunsService:
    def __init__(self, db: Session, tokenizer=None):
        self.repo = MatchingRunsRepository(db, tokenizer)
        self.retrieval = RetrievalService(db, TEMPLATE_V2, tokenizer)

    def profile(self, user: User, *, lock=False) -> CandidateProfile:
        profile = self.repo.lock(user.id) if lock else self.repo.profile(user.id)
        if profile is None:
            raise HTTPException(404, "Candidate profile not found")
        if profile.status != "active":
            raise HTTPException(409, "Candidate profile is inactive")
        return profile

    def configuration(self):
        try:
            return self.repo.configuration()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    def create(self, user: User) -> dict:
        try:
            profile = self.profile(user, lock=True)
            policy = self.configuration()
            captured = self.repo.capture(profile)
            if not captured["candidate_ready"]:
                raise HTTPException(409, "Current Template-v2 candidate embedding and approved inputs are required")
            # Supported Phase 5 retrieval is the only source of pool membership/order.
            pool = self.retrieval.jobs_for_user(user, 20)
            if len(pool) > 20 or len({x["job_id"] for x in pool}) != len(pool):
                raise HTTPException(409, "Invalid retrieval pool")
            for rank, row in enumerate(pool, 1):
                if (row["rank"], row["template_version"], row["model_id"], row["model_revision"]) != (
                        rank, TEMPLATE_V2, MODEL_ID, MODEL_REVISION):
                    raise HTTPException(409, "Retrieval policy/model/template mismatch")
                universe = next((x for x in captured["provenance"]["universe"] if x["job_id"] == str(row["job_id"])), None)
                if (not universe or row["job_input_hash"] != universe["representation_source_hash"]
                        or row["candidate_input_hash"] != captured["provenance"]["candidate_representation_source_hash"]):
                    raise HTTPException(409, "Retrieval source changed")
            retrieval_input = [{key: row[key] for key in ("rank", "job_id", "retrieval_similarity",
                "candidate_input_hash", "job_input_hash")} for row in pool]
            run_id = uuid4()
            self.repo.retire(profile.id, policy.id)
            selected_ids = {str(x["job_id"]) for x in pool}
            provenance = json_value({**captured["provenance"],
                "universe": [x for x in captured["provenance"]["universe"] if x["job_id"] in selected_ids],
                "full_universe_fingerprint": captured["universe_fingerprint"],
                "retrieval_order": retrieval_input, "capture_fingerprint": captured["fingerprint"]})
            run = MatchingRun(id=run_id, candidate_profile_id=profile.id, policy_id=policy.id,
                candidate_fingerprint=captured["candidate"]["fingerprint"], policy_fingerprint=POLICY_HASH,
                input_fingerprint=fingerprint({"capture": captured["fingerprint"], "retrieval": retrieval_input}),
                universe_fingerprint=captured["universe_fingerprint"], status="current", is_current=True,
                pool_limit=20, stale_missing_job_count=provenance["missing_job_embeddings"] + provenance["stale_job_embeddings"],
                engine_version=policy.engine_version, model_id=MODEL_ID, model_revision=MODEL_REVISION,
                template_version=TEMPLATE_V2, taxonomy_fingerprint=captured["taxonomy_fingerprint"],
                retrieval_fingerprint=fingerprint(retrieval_input),
                provenance_snapshot=bounded_snapshot(provenance, 262144, "run_provenance"))
            self.repo.add(run)
            self.repo.flush()
            candidate_anchors = {}
            for row in pool:
                state = captured["jobs"][str(row["job_id"])]
                try:
                    assessment = assess_inputs(captured["candidate"], state, captured["releases"])
                except InputConsistencyError as exc:
                    assessment = self.inconsistent_job(state, exc)
                self.persist_result(run, row, state, captured["candidate"], assessment, candidate_anchors)
            self.repo.flush()
            # Refresh ORM state too: identity-map caching must not hide a concurrent edit.
            self.repo.refresh()
            after = self.repo.capture(self.repo.profile(user.id))
            if (after["fingerprint"] != captured["fingerprint"]
                    or self.configuration().policy_hash != policy.policy_hash):
                raise HTTPException(409, "Inputs changed during run creation; no run was saved")
            response = self.read(user, run_id)
            self.repo.finish()
            return response
        except DBAPIError as exc:
            self.repo.rollback()
            code = getattr(exc.orig, "sqlstate", None)
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if code in {"40001", "40P01", "55P03"} or (code == "23505" and constraint == "uq_current_matching_run"):
                raise HTTPException(409, detail={"code": "matching_concurrency_conflict",
                    "message": "Concurrent matching-input change; reload before retrying"}) from exc
            if isinstance(exc, IntegrityError) or (code and code.startswith("22")):
                raise HTTPException(422, detail={"code": "matching_persistence_constraint",
                    "message": "Matching persistence constraint failed; the complete run was rolled back"}) from exc
            raise
        except SnapshotLimitError as exc:
            self.repo.rollback()
            raise HTTPException(413, detail={"code": "matching_snapshot_limit", "snapshot": str(exc),
                "message": "Evidence cannot fit the snapshot bound safely; the complete run was rolled back"}) from exc
        except Exception:
            self.repo.rollback()
            raise

    @staticmethod
    def inconsistent_job(state: dict, error: InputConsistencyError) -> dict:
        value = assess(tuple(Component(name, "unknown") for name in "RPOQ"),
                       inventory_complete=False, current=bool(state["inventory_current"]))
        value["reasons"] += (error.code,)
        return {"assessment": value, "groups": (), "evidence": (), "warnings": (error.code,),
            "consistency_error": error.code,
            "consistency_message": str(error),
            "consistency_reference": error.reference,
            "unknown_occurrences": [{"requirement_id": str(x["id"]), "classification": x["requirement_type"],
                "candidate_id": None, "support": None, "component": None, "reason_code": error.code}
                for x in state["skills"] if x["review_status"] != "rejected"]}

    def persist_result(self, run: MatchingRun, row: dict, state: dict, candidate: dict, adapted: dict,
                       candidate_anchors: dict | None = None) -> None:
        assessment = adapted["assessment"]
        if candidate_anchors is None:
            candidate_anchors = {}
        unknown, unknown_summary = reference_summary(list(adapted["unknown_occurrences"]), "skill_gap_results/atomic_assessments")
        occupation, occupation_summary = reference_summary([
            {key: x.get(key) for key in ("requirement_id", "candidate_id", "support", "reason_code")}
            for x in adapted["evidence"] if x.get("component") == "O"], "skill_gap_results/atomic_assessments")
        result = JobMatchResult(id=uuid4(), run_id=run.id, job_id=row["job_id"],
            job_fingerprint=fingerprint({"inventory": state["inventory"], "input": state["fingerprint"]}),
            input_fingerprint=fingerprint({"candidate": run.candidate_fingerprint, "job": state["fingerprint"],
                "inventory": state["inventory"], "policy": POLICY_HASH}),
            alignment_fraction=assessment["exact_fraction"], alignment_value=assessment["numeric"],
            provisional=assessment["provisional"], status="provisional" if assessment["provisional"] else "ready",
            retrieval_rank=row["rank"], retrieval_similarity=row["retrieval_similarity"],
            reason_code=adapted.get("consistency_error") or ("assessment_incomplete" if assessment["provisional"] else "candidate_confirmed_alignment"),
            reason_parameters=bounded_snapshot({"readiness_reasons": assessment["reasons"],
                "evidence_snapshot_version": "bounded-evidence-v1",
                "consistency_message": adapted.get("consistency_message"),
                "consistency_reference": adapted.get("consistency_reference"),
                "critical_missing_support": assessment["critical_missing_support"],
                "critical_penalty_cap_fraction": "1/10",
                "critical_deduction_fraction": exact(Fraction(1, 10) * assessment["critical_missing_support"])
                    if assessment["critical_missing_support"] is not None else None,
                "unknown_occurrences": unknown, "unknown_occurrence_summary": unknown_summary,
                "warnings": adapted["warnings"],
                "inventory_review": {key: state["inventory"][key] for key in (
                    "id", "review_status", "inventory_complete", "o_applicability", "o_reason", "q_applicability",
                    "q_reason", "source_fingerprint", "reviewer_pseudonym_snapshot", "reviewer_role_snapshot", "reviewed_at")
                    if state["inventory"] and key in state["inventory"]},
                "occupation_assessments": occupation, "occupation_summary": occupation_summary}, 8192, "result_reasons"))
        self.repo.add(result)
        self.repo.flush()
        for item in assessment["components"]:
            value, weight = item["value"], item["effective_weight"]
            self.repo.add(MatchScoreComponent(result_id=result.id, component=item["component"],
                status="not_applicable" if item["applicability"] == "not_applicable" else "unassessed" if value is None else "assessed",
                applicability=item["applicability"], numerator=value.numerator if value is not None else None,
                denominator=value.denominator if value is not None else None, base_weight=item["base_weight"],
                effective_weight_fraction=exact(weight), effective_weight_value=numeric(weight),
                value_fraction=exact(value), value=numeric(value), reason_code="component_assessment",
                reason_parameters=bounded_snapshot({"coverage_fraction": exact(item["coverage"]),
                    "contribution_fraction": exact(item["contribution"])}, 8192, "component_reasons")))
        work = [(group, [x for x in adapted["evidence"] if x.get("component") == group["component"]
                 and x.get("group_id") == group["group_id"]
                 and (group["group_id"] is not None or x["requirement_id"] == group["assessments"][0]["requirement_id"])])
                for group in adapted["groups"]]
        work += [({"group_id": None, "component": None, "operator": "SINGLE", "critical": False,
                   "status": "unassessed", "support": None, "warnings": (atom["reason_code"],)}, [atom])
                 for atom in adapted["unknown_occurrences"]]
        requirement_anchors = {}
        for group, evidence in work:
            support = group["support"]
            gap = SkillGapResult(id=uuid4(), result_id=result.id, group_id=UUID(group["group_id"]) if group["group_id"] else None,
                support_fraction=exact(support), support_value=numeric(support), critical=group["critical"],
                status=group["status"], reason_code=adapted.get("consistency_error") or (
                    "unresolved_inventory_occurrence" if group["component"] is None else "group_assessment"),
                reason_parameters=bounded_snapshot({"component": group["component"], "operator": group["operator"],
                    "warnings": group["warnings"]}, 8192, "gap_reasons"))
            atoms, candidate_refs, requirement_refs = [], {}, {}
            for atom in evidence:
                value = atom["support"]
                atomic_id = uuid4()
                # Evidence prose is stored once, at a typed source anchor. All
                # individual comparison decisions/IDs remain relational rows.
                parameters = {k: v for k, v in atom.items() if k not in {
                    "candidate_evidence_reference", "requirement_evidence_reference"}}
                member = next((m for m in state["members"] if str(m["id"]) == atom.get("member_id")), {})
                for side, source, is_fact, anchors, refs in (
                    ("candidate", candidate, group["component"] in {"O", "Q"}, candidate_anchors, candidate_refs),
                    ("requirement", state, group["component"] == "O" or bool(member.get("job_matching_fact_id")),
                     requirement_anchors, requirement_refs)):
                    source_id = atom.get("candidate_id" if side == "candidate" else "requirement_id")
                    if source_id is None:
                        continue
                    source_row = next((x for x in source["facts" if is_fact else "skills"] if str(x["id"]) == source_id),
                                      {"id": source_id, "source_record_missing": True})
                    key = ("fact" if is_fact else "skill", source_id, fingerprint(source_row))
                    anchor_id = anchors.setdefault(key, str(atomic_id))
                    reference = {"id": source_id, "source_kind": key[0], "anchor_atomic_id": anchor_id,
                                 "source_snapshot_sha256": key[2]}
                    if source_row.get("extracted_term_id"):
                        reference["extracted_term_id"] = str(source_row["extracted_term_id"])
                    refs[key] = reference
                    parameters[side + "_evidence_anchor_id"] = anchor_id
                    if anchor_id == str(atomic_id):
                        parameters[side + "_evidence"] = self.evidence_excerpt(source_row, source["taxonomy"])
                atoms.append(SkillGapAtomicResult(id=atomic_id, gap_id=gap.id,
                    member_id=UUID(atom["member_id"]) if atom.get("member_id") else None,
                    occurrence_fingerprint=fingerprint({"candidate": atom.get("candidate_id"),
                        "requirement": atom["requirement_id"], "input": run.candidate_fingerprint}),
                    support_fraction=exact(value), support_value=numeric(value), reason_code=atom["reason_code"],
                    reason_parameters=bounded_snapshot(parameters, 8192, "atomic_reasons")))
            candidates, c_summary = reference_summary(list(candidate_refs.values()), "skill_gap_atomic_results")
            requirements, r_summary = reference_summary(list(requirement_refs.values()), "skill_gap_atomic_results")
            group_review = next((x for x in state["groups"] if str(x["id"]) == group["group_id"]), {})
            gap.evidence_snapshot = bounded_snapshot({"group_id": group["group_id"],
                "candidate_confirmed_evidence": candidates, "candidate_reference_summary": c_summary,
                "reviewed_requirements": requirements, "requirement_reference_summary": r_summary,
                "group_review": {key: group_review[key] for key in ("id", "operator", "classification", "critical",
                    "reviewer_pseudonym_snapshot", "reviewer_role_snapshot", "reviewed_at", "source_fingerprint")
                    if key in group_review}}, 16384, "gap_evidence")
            self.repo.add(gap)
            self.repo.flush()
            for atom in atoms:
                self.repo.add(atom)

    @staticmethod
    def evidence_excerpt(row: dict, taxonomy: dict) -> dict:
        keys = ("id", "extracted_term_id", "raw_text", "normalized_text", "skill_type", "fact_type",
                "statement", "completion", "duration_months", "field", "scope", "evidence_reference",
                "evidence_sentence", "review_status", "cv_document_id", "taxonomy_concept_id", "taxonomy_release_id",
                "source_fingerprint", "reviewer_pseudonym_snapshot", "reviewer_role_snapshot", "reviewed_at",
                "source_record_missing", "candidate_profile_id", "job_id", "source", "confidence_score")
        value = json_value({key: row[key] for key in keys if key in row})
        value["source_snapshot_sha256"] = fingerprint(row)
        value["comparison_fingerprints"] = {key: hashlib.sha256(normalize(row[key]).encode()).hexdigest()
            for key in ("normalized_text", "statement", "field", "scope") if key in row}
        term = next((x for x in taxonomy.get("terms", []) if x["id"] == row.get("extracted_term_id")), {})
        if term.get("cv_document_id"):
            value["cv_document_id"] = str(term["cv_document_id"])
        if term:
            value["extraction_provenance"] = {key: term[key] for key in (
                "id", "extraction_method", "source_section", "start_char", "end_char") if key in term}
        concepts = {str(x["id"]): x for x in taxonomy["concepts"]}
        value["taxonomy_links"] = [{"concept_id": link["concept_id"],
            "release_id": concepts[str(link["concept_id"])]["taxonomy_version_id"],
            "match_method": link["match_method"], "taxonomy_confidence": link["confidence_score"]}
            for link in taxonomy["links"] if row.get("extracted_term_id")
            and link["extracted_term_id"] == row["extracted_term_id"] and str(link["concept_id"]) in concepts]
        value = json_value(value)
        value["text_omissions"] = {}
        value["full_source_required_for_text_reconstruction"] = False
        for key, cap in (("evidence_sentence", 256), ("statement", 256), ("scope", 128), ("field", 128),
                         ("raw_text", 255), ("normalized_text", 255)):
            if len(json.dumps(value, ensure_ascii=False).encode()) <= 3200:
                break
            if key in value and len(value[key]) > cap:
                value["text_omissions"][key] = {"original_sha256": hashlib.sha256(row[key].encode()).hexdigest(),
                    "original_characters": len(row[key]), "retained_characters": cap}
                value[key] = value[key][:cap]
                value["full_source_required_for_text_reconstruction"] = True
        # Extreme Unicode/prose fields can still exceed the excerpt budget.
        # Preserve all IDs/references/identity hashes, and explicitly omit prose.
        for key in ("evidence_sentence", "statement", "scope", "field", "raw_text", "normalized_text"):
            if len(json.dumps(value, ensure_ascii=False).encode()) <= 3200:
                break
            if key in value:
                value["text_omissions"][key] = {"original_sha256": hashlib.sha256(row[key].encode()).hexdigest(),
                    "original_characters": len(row[key]), "retained_characters": 0}
                value[key] = ""
        value["full_source_required_for_text_reconstruction"] = bool(value["text_omissions"])
        return bounded_snapshot(value, 3200, "evidence_excerpt")

    def current(self, user: User) -> dict:
        profile = self.profile(user)
        self.configuration()
        run = self.repo.current(profile.id)
        if run is None:
            raise HTTPException(404, "No current matching run; use explicit POST to create one")
        return self.read(user, run.id)

    def read(self, user: User, run_id: UUID) -> dict:
        profile = self.profile(user)
        self.configuration()  # Never trust an installed configuration merely because it loaded.
        run = self.repo.run(run_id, profile.id)
        if run is None:
            raise HTTPException(404, "Matching run not found")
        current = False
        captured = None
        reasons = []
        if run.status != "unreplayable":
            captured = self.repo.capture(profile)
            current = bool(run.is_current and run.status == "current" and captured["candidate_ready"]
                and captured["fingerprint"] == (run.provenance_snapshot or {}).get("capture_fingerprint")
                and run.policy_fingerprint == POLICY_HASH and run.template_version == TEMPLATE_V2
                and run.taxonomy_fingerprint == captured["taxonomy_fingerprint"]
                and run.universe_fingerprint == captured["universe_fingerprint"]
                and run.candidate_fingerprint == captured["candidate"]["fingerprint"]
                and run.retrieval_fingerprint == fingerprint((run.provenance_snapshot or {}).get("retrieval_order")))
        if not current:
            reasons.append("history_unreplayable" if run.status == "unreplayable" else "inputs_stale_or_historical")
        results = [self.result_view(row, current, run.status == "unreplayable") for row in self.repo.results(run.id)]
        # Exact fractions determine order; a provisional row never receives an invented zero.
        results.sort(key=result_order_key)
        ready = sum(x["alignment_fraction"] is not None for x in results)
        provenance = run.provenance_snapshot or {}
        live = captured["provenance"] if captured else provenance
        stale_missing_count = live.get("missing_job_embeddings", 0) + live.get("stale_job_embeddings", 0)
        if stale_missing_count:
            reasons.append("eligible_universe_incomplete")
        if len(results) < 20:
            reasons.append("retrieval_pool_incomplete")
        return {"run_id": run.id, "policy_version": POLICY_VERSION, "policy_hash": run.policy_fingerprint,
            "engine_version": run.engine_version, "status": run.status if current or run.status in {"unreplayable", "historical"} else "stale",
            "current": current, "created_at": run.created_at, "input_fingerprint": run.input_fingerprint,
            "candidate_fingerprint": run.candidate_fingerprint, "taxonomy_fingerprint": run.taxonomy_fingerprint,
            "retrieval_fingerprint": run.retrieval_fingerprint, "provenance": run.provenance_snapshot or {},
            "retrieval": {"template_version": run.template_version, "model_id": run.model_id,
                "model_revision": run.model_revision, "pool_limit": run.pool_limit,
                "stale_missing_job_count": stale_missing_count,
                "recorded_stale_missing_job_count": run.stale_missing_job_count,
                "missing_job_embeddings": live.get("missing_job_embeddings"),
                "stale_job_embeddings": live.get("stale_job_embeddings"),
                "eligible_job_count": live.get("eligible_jobs"), "dense_numeric_weight": 0,
                "universe_fingerprint": run.universe_fingerprint},
            "readiness": {"warnings": reasons, "score_ready_jobs": ready,
                "provisional_jobs": len(results) - ready, "ranking_evaluation_ready": current and len(results) == 20 and ready == 20},
            "ordering": "UI-only scored-first ordering; not an evaluated ranking" if ready != 20 else "complete_pool_alignment_order",
            "results": results}

    def result_view(self, row: JobMatchResult, current: bool, unreplayable: bool) -> dict:
        redacted = unreplayable or row.status == "unreplayable"
        visible_score = current and row.status == "ready" and not row.provisional
        components = self.repo.components(row.id)
        gaps = self.repo.gaps(row.id)
        view = {"result_id": row.id, "job_id": row.job_id, "current": current,
            "status": row.status if current or redacted else "stale", "provisional": not visible_score,
            "alignment_score": str(decimal_value(Fraction(row.alignment_fraction), 2)) if visible_score else None,
            "alignment_numeric": str(row.alignment_value) if visible_score else None,
            "alignment_fraction": row.alignment_fraction if visible_score else None,
            "recorded_provisional": row.provisional,
            "recorded_alignment_fraction": row.alignment_fraction,
            "original_retrieval_rank": row.retrieval_rank, "retrieval_similarity": str(row.retrieval_similarity),
            "input_fingerprint": row.input_fingerprint, "reason_code": row.reason_code,
            "reason_parameters": {} if redacted else row.reason_parameters,
            "components": [{"component": x.component, "status": x.status, "applicability": x.applicability,
                "numerator": str(x.numerator) if x.numerator is not None else None,
                "denominator": str(x.denominator) if x.denominator is not None else None,
                "base_weight": x.base_weight, "effective_weight_fraction": x.effective_weight_fraction,
                "effective_weight_value": str(x.effective_weight_value) if x.effective_weight_value is not None else None,
                "value_fraction": x.value_fraction, "value": str(x.value) if x.value is not None else None,
                "coverage_fraction": None if redacted else x.reason_parameters.get("coverage_fraction"),
                "contribution_fraction": None if redacted else x.reason_parameters.get("contribution_fraction"),
                "reason_code": x.reason_code, "reason_parameters": {} if redacted else x.reason_parameters} for x in components],
            "gaps": [{"group_id": x.group_id, "status": x.status, "critical": x.critical,
                "support_fraction": x.support_fraction, "reason_code": x.reason_code,
                "reason_parameters": {} if redacted else x.reason_parameters,
                "evidence": {} if redacted else x.evidence_snapshot,
                "atomic_assessments": [{"id": a.id, "member_id": a.member_id,
                    "support_fraction": a.support_fraction, "reason_code": a.reason_code,
                    "reason_parameters": {} if redacted else a.reason_parameters}
                    for a in self.repo.atomic(x.id)]} for x in gaps]}
        for label, classification in (("missing_required", "required"), ("missing_preferred", "preferred")):
            view[label] = [x["group_id"] for x in view["gaps"] if x["status"] == "Missing"
                and x["evidence"].get("group_review", {}).get("classification") == classification]
        view["gaps"].sort(key=lambda x: (str(x["group_id"] or ""),
            str(next(iter(x["evidence"].get("reviewed_requirements", [])), {}).get("id", ""))))
        view["unassessed_requirements"] = [x["group_id"] or
            next(iter(x["evidence"].get("reviewed_requirements", [])), {}).get("id")
            for x in view["gaps"] if x["status"] == "unassessed"]
        return view
