"""Source-bound inventory checks; never part of retrieval or policy arithmetic."""
import hashlib

from app.matching.policy import compatibility_family, normalize

INPUT_ADAPTER_VERSION = "phase6-inputs-v2"
CAPABILITY_TYPES = {"skill", "tool", "domain_knowledge", "language"}


def cleaned_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manual_conflict(state: dict) -> str | None:
    """Recheck all extracted review states; a later reprocess must not bypass entry."""
    seen = {(compatibility_family(x["skill_type"]), normalize(x["normalized_text"]))
            for x in state["skills"] if x["skill_type"] in CAPABILITY_TYPES}
    for row in state.get("manual_capabilities", []):
        if row["cleaned_description_sha256"] != state["cleaned_description_sha256"]:
            return "manual_source_mismatch"
        key = (compatibility_family(row["skill_type"]), normalize(row["normalized_text"]))
        if key in seen:
            return "manual_capability_conflict"
        seen.add(key)
    return None
