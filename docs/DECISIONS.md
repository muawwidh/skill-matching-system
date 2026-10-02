# Architecture and Methodology Decisions

## D001 — Layered Architecture

Use:

Frontend
→ API Routes
→ Services
→ Repositories
→ Database/domain modules

Reason:

Maintain separation of concerns and testability.

## D002 — PostgreSQL

PostgreSQL is the main persistent database.

Reason:

Relational integrity and future pgvector integration.

## D003 — Alembic

All schema evolution uses Alembic migrations.

Do not modify previously applied migrations to introduce new schema changes.

## D004 — Local ESCO/O*NET Storage

ESCO and O*NET releases are imported and stored locally.

The matching system must not depend on live taxonomy APIs for every match.

Reason:

- reproducibility
- performance
- availability
- version control
- thesis evaluation consistency

## D005 — Sample Taxonomies

Bundled ESCO/O*NET samples exist only for development/testing.

They must remain clearly identified as sample releases.

## D006 — Taxonomy Confidence

High-confidence deterministic taxonomy links may be automatically approved.

Uncertain mappings remain reviewable.

Multiple ranked candidates may be stored.

Reason:

Incorrect taxonomy normalization can negatively affect downstream
matching and gap analysis.

## D007 — Extraction Evidence

Repeated term occurrences may remain separately stored when each represents
different evidence.

Candidate-facing normalized skills should be deduplicated separately.

## D008 — PDF Baseline

Readable PDF text extraction is supported.

PDF text normalization is used before section detection where appropriate.

OCR is not currently a baseline requirement.

## D009 — Dense Retrieval Is Not Final Scoring

Vector similarity in Phase 5 is used only to retrieve top-N relevant jobs.

It is not the final match score.

## D010 — Early Matching Is Transitional

The matching implementation created after Phase 3 is a prototype for later
Phase 6 development.

It should be expanded/refactored rather than treated as the completed
matching methodology.

## D011 — Versioned Final Scoring

Phase 6 scoring configuration must be configurable/versioned.

Reason:

Reproducibility and evaluation.

## D012 — Explanation Grounding

Match and skill-gap explanations must derive from stored structured evidence.

Unsupported explanation text is not acceptable.

## D013 — Data Minimization

Matching excludes irrelevant personal attributes such as:

- age
- gender
- religion
- nationality
- marital status
- photographs

## D014 — Administrative Separation

System-wide logs, taxonomy management and similar administrative data are
restricted to administrator/researcher users.

## D015 — Development Taxonomy Docker Mount

Repository ./data is mounted as /data inside the backend development
container.

Reason:

Phase 4 sample taxonomy loading resolves data from /data/sample.

## D016 - Pinned Native Package Contracts

Native package support is pinned to ESCO 1.2.1 classification English CSV and
O*NET 29.0 tab-delimited TXT and O*NET 31.0 CSV. Exact files/headers and optional dependencies are
explicit contracts, not heuristic column aliases. Other versions/formats require
their own implementation and verification. Legacy flattened formats remain
separate development/interchange paths. Full-package PostgreSQL evidence is
required in addition to fixtures before claiming official-format support.

## D017 - Lossless Structured Taxonomy Data

ESCO relationships have directed, same-release endpoints enforced by composite
foreign keys. Original relationship rows preserve essential/optional and skill
type semantics. O*NET rows retain typed identifiers and exact numeric values plus
complete source fields and release-scoped scale/category reference records.
Source metadata is retained for reproducibility, not used as an unsupported score.

ESCO v1.2.1 repeats some concept URIs with only modifiedDate differences. Merge
these into one concept while retaining every source row and reporting merged
counts. Conflicting semantic fields fail rather than choosing a row silently.

## D018 - Atomic Release Replacement

Validate before writing; serialize same-source PostgreSQL imports with a transaction
advisory lock. Replacement and activation commit as one transaction. Any failure,
including after deletion or partial inserts, restores the previous release and its
dependent mappings/reviews. Successful same-version replacement retains the prior
documented lifecycle: dependencies may cascade away, requiring mapping reimport
and extracted-term relinking. No automatic review-decision migration is implied.

## D019 - Explicit Taxonomy Selection and Review Audit

The approved link is the authoritative selection for a term_source/extracted_term_id
pair. A replaced approval becomes `superseded`: previously selected, not semantically
incorrect. Only explicit rejection marks a suggestion incorrect. Rejecting the
selected candidate removes its approved link; rejecting alternatives preserves it.

Selection replacement requires explicit confirmation against the current selection
token. PostgreSQL transaction advisory locks serialize term reviews and relinking.
Selection, status reconciliation and before/after audit snapshots commit atomically.
Repeated identical reviews are no-ops, preserving original timestamps and history.

Audit snapshots retain concept labels/identifiers and previous reviewer information.
They intentionally have no candidate/term foreign keys, so reprocessing or release
replacement does not erase recorded history. Reviewer deletion sets the actor FK to
null. This preserves history, not live links: D018 replacement semantics are unchanged.
No historical events are fabricated and migration 0007 does not repair legacy rows.
Legacy inconsistency is exposed for an explicit subsequent review through the UI.

## D020 - Candidate Skill Presentation Groups

Candidate-facing consolidation is a read projection, not evidence deduplication.
Approved taxonomy links group by concept UUID plus taxonomy release UUID. Source,
version and preferred label are shown; neither equal labels nor cross-taxonomy
mappings imply identity. Unlinked occurrences group by the exact pair of skill_type
and lowercase stored normalized_text, reusing extraction/save normalization without
additional punctuation stripping, fuzzy comparison or alias inference. Linked and
unlinked occurrences are never forced into one group.

Every occurrence keeps its ID, evidence, confidence and extraction review decision.
Only extraction-approved occurrences provide confirmed support in this presentation;
pending/rejected evidence is not confirmed by a taxonomy mapping. This does not
redefine matching scores. Individual corrections invalidate that occurrence's mapping
and suggestions, update its term for later relinking, and preserve evidence/history.
Status-only extraction review does not change taxonomy review. Legacy text/term
mismatches are presented without taxonomy identity until corrected/relinked.

## D021 - Separate O*NET Release Adapters

Dispatch 29.0 TXT and 31.0 CSV to separate version-pinned adapters sharing only
archive safety and transactional persistence. The 31.0 manifest declares every
supported dataset and its identity columns. Do not retrofit CSV naming/semantics
onto the verified TXT adapter or imply unsupported release compatibility.

Preserve every CSV row, including multi-endpoint relationships, in structured
source_data. Materialize content-reference nodes and explicitly directed binary
links using the rules in onet-31-contract.md; do not flatten triple/task records
into interchangeable labels. Source rows remain authoritative for richer semantics.
This extends coverage without changing the release replacement lifecycle or scoring.
