# Project State

Last updated: 2026-11-11

## Repository

Main branch:

`main`

Final Phase 4 checkpoint (committed and pushed):

`1aba426 Complete verified Phase 4 taxonomy integration`

Earlier Phase 4 implementation checkpoint (not the final closure checkpoint):

`24dd9a7 Complete phase 4 taxonomy integration`

Initial Git baseline:

`cf40546 Establish phases 1-3 and matching baseline`

## Current Phase

Phase 6 — Matching and Skill-Gap Analysis

Implementation status:

ACCEPTED METHODOLOGY/DESIGN CHECKPOINT ONLY. matching-policy-v1 and its
evaluation protocol were accepted on 2026-11-10 following independent review
and are frozen before implementation and Phase 6 rankings (D034). No Phase 6
application implementation has begun. Phase 6 is not complete.

Current status:

PHASE 6 METHODOLOGY ACCEPTED; DOCUMENTATION PROMOTION UNCOMMITTED FOR INSPECTION

Phase 5 remains COMPLETE as a repository/methodology checkpoint, including
the accepted D033 run-specific scoped-isolation exception. Its frozen
artifacts, labels, rankings, metrics and results remain unchanged. Deployment
is a separate operational checkpoint, not implied by methodology acceptance.

Repository head: `0008_dense_retrieval`.
Isolated successfully verified head: `0008_dense_retrieval`.
Developer database head: last independently observed `0008_dense_retrieval`;
not queried or modified for this documentation promotion.
`0009_explainable_matching` is proposed and does not exist yet.

No Phase 6 reviewed facts, inventory sign-offs, scores, rankings or evaluations
exist yet. The legacy matcher remains prototype behavior, not the final Phase 6
engine; existing candidate_job_matches are not reinterpreted.

Next authorized work is Phase 6 Checkpoint 1: policy engine, reviewed-fact and
inventory contracts/APIs, and migration 0009, subject to its required distinct-
value audit and safe handling plan. Implementation is not performed in this
documentation task. Frozen-corpus fact entry remains a separate controlled
data-preparation activity, not application implementation.

Accepted references: docs/phase6-explainable-matching.md and
docs/phase6-evaluation-protocol.md. The two later checkpoints before evaluation
cover service/persistence/currentness and minimal forms/explanation UI; the
fourth checkpoint covers separately controlled fact/policy freezes/evaluation.

Phase 4 closure combines repository test/package evidence with user-reported
deployed browser/runtime acceptance. The Phase 5 work below is limited to
candidate-profile to job retrieval; it changes neither the Phase 4 lexical
linker/reviews nor the earlier rule-based matching scores.

## Important Development History

After Phase 3, an early candidate-job matching implementation was built
and temporarily referred to as Phase 4.

The original requirements were subsequently rechecked.

The official Phase 4 is Taxonomy Integration.

Therefore the repository currently contains:

- completed Phase 1
- completed Phase 2
- completed Phase 3
- completed Phase 4 taxonomy integration
- completed Phase 5 dense retrieval with accepted frozen evaluation and
  explicitly documented corpus/coverage/isolation limitations
- early/basic matching functionality conceptually belonging to Phase 6

The existing matching prototype is NOT the final Phase 6 implementation.

## Phase 1

Status: COMPLETE

Migration:

0001_foundation_auth

Implemented:

- project structure
- FastAPI
- React/TypeScript/Vite
- Tailwind
- PostgreSQL
- Docker
- Nginx
- authentication
- refresh tokens
- RBAC foundation
- SQLAlchemy
- Alembic
- configuration
- health endpoint
- backend tests
- frontend build
- initial documentation

## Phase 2

Status: COMPLETE

Migration:

0002_document_processing

Implemented:

- candidate profile
- CV paste
- CV upload
- PDF parsing with pypdf
- DOCX parsing
- TXT parsing
- validation
- processing consent
- text cleaning
- PDF text normalization
- section detection
- job creation/import
- job section detection
- processing logs
- raw/cleaned CV previews
- full section display

Scanned PDF OCR is not currently part of the baseline.

Stability Batch 4 updates PDF normalization at upload/parsing: only genuine
line headings/delimiters and strongly structured flattened uppercase heading
runs create sections. Pre-heading body text is retained as `full_text` with
valid offsets. Existing uploaded PDFs keep their stored text on ordinary
`process_cv`: reprocessing does not rerun parsing or repair legacy PDF
normalization. Affected PDFs require a new upload for corrected stored text;
the new CV lifecycle does not inherit prior reviews.

## Phase 3

Status: COMPLETE

Migration:

0003_skill_extraction

Implemented:

- local skill dictionary
- dictionary extraction
- regex extraction
- evidence capture
- confidence scores
- source section tracking
- extracted candidate terms
- extracted job terms
- candidate skills
- job skills
- candidate review
- approve/reject
- editable extracted skill name
- compact evidence display
- automatic extraction during processing

Repeated terms may exist in extracted_candidate_terms because each
occurrence may preserve separate evidence.

Candidate-facing CV skills now have a consolidated read view with expandable
occurrences (see Phase 4 below); stored extraction occurrences remain separate.
Newly persisted candidate/job extracted terms identify extractor contract `v2`
in `extraction_method` (`dictionary@v2`, `regex@v2`, or optional
`spacy_phrase_matcher@v2`). Dictionary boundaries now admit ordinary terminal
punctuation while protecting technical-name continuations. Existing terms are
not rewritten. Every extraction made before Stability Batch 4 has a legacy
`extraction_method` value. Because that field is part of Batch 2's complete
occurrence reconciliation key, reprocessing a pre-v2 CV replaces all its
legacy extraction occurrences even when visible text and offsets are unchanged.
Approved, rejected and pending extraction reviews reset to newly extracted
`pending` skills. A previously rejected skill may temporarily enter the
transitional prototype matcher, which includes pending but excludes rejected
skills. Taxonomy candidates and selected links for replaced terms are removed;
taxonomy review audit events remain append-only. The candidate embedding is
marked stale by the existing invalidation lifecycle. All reprocessed pre-v2
evidence must be reviewed and relinked again before indexing or evaluation.
This contract boundary does not safely migrate reviews. There is no requirement
to reprocess reviewed legacy CVs immediately: leave them untouched unless
deliberately regenerating and re-reviewing their evidence.

## Early Matching Prototype

Migration:

0004_candidate_job_matching

Status:

TRANSITIONAL PROTOTYPE

Implemented:

- candidate-job match persistence
- basic candidate/job skill comparison
- basic required/preferred weighting
- matched skills
- missing skills
- basic match percentage
- recommendation endpoints
- Candidate Match frontend panel

This DOES NOT replace final Phase 6.

It currently lacks the complete planned:

- dense retrieval flow
- multi-component versioned scoring
- taxonomy-aware partial coverage
- occupation alignment
- qualification/experience alignment
- critical-skill penalties
- complete evidence-backed explanation system

## Phase 4 — Taxonomy Integration

Migration status at Phase 4 closure (historical snapshot, not current repository head):

- Repository migration head: `0007_taxonomy_review_audit`.
- Last successfully verified revision: `0007_taxonomy_review_audit`, isolated PostgreSQL 16,
  including populated 0005 upgrade and preservation of existing reviews from 0006.
- Developer local Compose database head: `0007_taxonomy_review_audit`, reported
  from deployed runtime on 2026-10-02 and last independently observed through a
  read-only query on 2026-10-06; not queried or changed during Stability Batch 3.

Status:

COMPLETE (2026-10-02)

Implemented in the current codebase:

- taxonomy sources
- taxonomy versions
- taxonomy concepts
- taxonomy labels
- O*NET occupations
- ESCO–O*NET mappings
- taxonomy link candidates
- approved taxonomy links
- generic JSON/CSV/TSV/TXT taxonomy import adapter
- bundled development sample imports
- taxonomy search
- taxonomy concept lookup APIs
- occupation lookup APIs
- taxonomy version listing
- ESCO–O*NET mapping listing
- normalized label comparison
- preferred-label exact matching after normalization
- alternative-label exact matching after normalization
- RapidFuzz fuzzy matching
- confidence scoring
- ranked link candidates
- automatic approval of strong deterministic matches only when one concept has
  the unique highest confidence above the existing threshold
- administrator/researcher review workflow
- automatic taxonomy linking during CV/job processing
- taxonomy management frontend
- role-management utility

Additional Phase 4 implementation:

- strict ESCO 1.2.1 English CSV ZIP, O*NET 29.0 TXT ZIP and O*NET 31.0 CSV ZIP contracts
- ESCO relationships with original direction and essential/optional distinction
- same-release relationship foreign keys
- structured O*NET occupation data, ratings and reference records
- bounded archive validation (uploaded/member/total bytes and member count)
- atomic release replacement and explicit rollback after write failures
- source-scoped PostgreSQL transaction advisory locks
- persisted per-file import reports and hashes
- paginated relationship and occupation-data lookup APIs
- representative fixtures including optional O*NET files
- PostgreSQL migration/replacement/rollback/review tests
- full-package verification CLI and checked-in evidence reports

### Official taxonomy support boundaries

The pinned contracts are ESCO 1.2.1 classification English CSV ZIP, O*NET 29.0
native TXT ZIP and O*NET 31.0 CSV ZIP only. ESCO 1.2.0, O*NET 31.0 TXT and other
O*NET versions are not supported claims.
Exact required/optional files and columns are documented in taxonomy-integration.md
and onet-31-contract.md with the checked-in 31.0 manifest.
Unknown package files are reported as skipped; this is not ingestion of every
dataset/domain that either publisher distributes. No embeddings or final scoring
were added.

Complete supplied ESCO 1.2.1 and downloaded O*NET 29.0 packages have passed import
and persisted-count reconciliation in isolated PostgreSQL. Evidence is in
docs/verification and docs/phase4-verification.md. ESCO was supplied as an extracted
directory without an embedded version manifest; the original download ZIP checksum
is unavailable. Its report records a reconstructed ZIP checksum plus all original
member hashes, not a claimed original distribution ZIP checksum.

ESCO timestamp-only duplicate rows are merged by URI while preserving all source
rows: 21 duplicate skill rows and 4 duplicate occupation rows. Other conflicting
duplicates fail. Input/inserted/merged counts are reported separately.

O*NET datasets include occupations, elements, scales, skills, knowledge, abilities,
work activities, tasks/ratings/categories, tools/technology, education/experience
and category definitions. Optional alternate titles and job zones/reference data
are implemented and tested. Full source rows preserve interpretation metadata.

The legacy flattened JSON/CSV/TSV/TXT adapter remains available for development
and interchange. It is not general official-package compatibility.

### O*NET 31.0 CSV implementation and verification (2026-10-02)

Separate ONET-31.0-csv dispatch retains the verified ONET-29.0-txt adapter unchanged.
All 45 supplied CSV datasets and every source field are preserved, including separate
Essential/Transferable Skills, education/training categories, directional relationships
and intact multi-endpoint rows. Dataset-specific identity keys avoid the documented
software-skill and binary-relationship collisions. Unknown members are explicitly
reported; only Read Me.txt is skipped in this package after release validation.

Full package SHA-256:
`55033fc68b4c13ec23e7f74dc6378660f6e854e75d55d6e333ae0a761d3987cd`.
Evidence: docs/verification/onet-31.0.json. Initial import and same-version replacement
each reconciled all 1,120,006 source/database records, comparing every source field in
fresh PostgreSQL sessions. Materialized 4,022 concepts (including 1,016 occupations)
and 20,262 directed relationships; zero unresolved references. Initial verification
74.576 seconds, replacement 101.420 seconds, total 176.141 seconds. The dedicated
verification schema in phase4_verify was removed afterward.

Final complete backend suite: **146 passed**, PostgreSQL checks enabled; no skipped
checks in this run. Frontend production build and git diff --check passed. Coverage
includes all manifest files/headers, UTF-8/BOM/quoting, malformed CSV, extra columns,
archive safety, exact historical collision counts, references, negative scales,
categories, directed links, and replacement/post-write rollback. Existing 29.0
regressions remain intact.

No new migration: repository and isolated verified head remain
0007_taxonomy_review_audit. Developer DB revision was not rechecked or changed.
No developer records were imported, and no local Docker deployment was performed.
29.0 historical verification evidence is unchanged. Attribution and exact per-dataset
counts are in onet-31-contract.md; representative fixtures are explicitly distinct
from full-package evidence. Subsequent user-reported browser/runtime acceptance is
recorded in the closure section below. No embedding/retrieval/scoring work was added.

### Phase 4 verification coverage

Verified by automated/end-to-end tests:

- bundled JSON development sample import
- taxonomy search
- concept lookup
- ESCO–O*NET sample mappings
- automatic taxonomy linking
- fuzzy review candidates
- role protection
- approval workflow

Additional verification completed:

- CSV taxonomy import
- TSV taxonomy import
- TXT taxonomy import
- native ESCO 1.2.1 English package fixtures and full supplied dataset
- native O*NET 29.0 TXT package fixtures and complete downloaded package
- optional O*NET file ingestion and validation
- PostgreSQL upgrade from populated 0005, downgrade preservation and re-upgrade
- PostgreSQL FK/uniqueness, same-version replacement and post-write rollback
- PostgreSQL persisted approval and rejection decisions
- archive safety, permissions, intended authenticated read APIs

The full backend suite and frontend production build have passed. PostgreSQL
tests skip explicitly as UNVERIFIED when their isolated database URL is absent.
The new backend image was built and its isolated API health endpoint passed.
That image/health verification predates the review consistency fix below.
Developer application containers/data were not upgraded or replaced by this fix.

### Review consistency blocker (resolved at closure)

Manual acceptance exposed two approved candidate statuses for one extracted term,
although only the second candidate was selected by approved_taxonomy_links.
Code inspection also found rejection could leave a selected link intact.

Implemented fix:

- approved_taxonomy_links is the authoritative selection for each source/term pair
- replacing a selection marks the previous approval `superseded`, not rejected
- rejecting the selected candidate removes its link; rejecting an alternative preserves it
- PostgreSQL term-scoped locks serialize reviews and candidate replacement
- explicit replacement confirmation and a selection token prevent silent/stale replacements
- repeated identical actions are idempotent and do not manufacture audit events
- audit events store actor, time and before/after snapshots in the same transaction
- grouped Pending/Selected/All views expose alternatives, selection and review history
- legacy inconsistent statuses are flagged on read, never automatically repaired
- administrator/researcher-only review/history endpoints preserve candidate restrictions

Verification: complete backend suite **71 passed** with isolated PostgreSQL enabled;
frontend production build passed. Regression coverage includes fresh PostgreSQL
sessions, concurrent approvals, replacement, both rejection paths, repetition,
source/term isolation, audit-write rollback, API permissions and additive 0006-to-0007
migration preserving existing inconsistent records. No developer records were changed.
Subsequent user-reported deployed acceptance verified approval, rejection,
replacement, superseded state, persistence after refresh and review history.

### Candidate skill consolidation (2026-10-01)

The CV page previously rendered every extracted skill row separately, without
taxonomy identity in its response. A new ownership-checked
`GET /cvs/{document_id}/skill-groups` read endpoint groups occurrences by approved
concept UUID and release UUID, exposing preferred label, external ID, source and
version. Equal labels in distinct concepts/releases stay separate. Unlinked skills
group only by exact lowercase stored normalized_text plus skill_type, not fuzzy
similarity or cross-taxonomy equivalence. Linked and unlinked groups stay separate.

Each group retains every occurrence ID, evidence, confidence and extraction review
status. The CV-only panel expands occurrences for individual edits/approval/rejection;
mixed statuses and all-rejected groups remain visible. Only extraction-approved
occurrences count as confirmed support in this view. Taxonomy approval is independent.
This presentation count does not change the existing matching prototype or scores.

The existing flat read and save response formats remain available. CV saves now
validate occurrence IDs against that CV and return its skills, rather than all
profile skills. Existing profile-level manual skills remain profile-scoped. Drafts
and actions use occurrence IDs. Saved changes refetch groups; taxonomy review
invalidates CV queries, and the CV view also refreshes on focus/every 30 seconds.
Draft changes are preserved separately during background refreshes.

Text/normalization/type corrections clear only that occurrence's taxonomy selection
and suggestions, and update its extracted term for subsequent explicit relinking.
Evidence and audit history remain stored. Status-only reviews leave taxonomy links
unchanged. Reads treat legacy skill/term text mismatches as unlinked without repairs.
No administrative review history is exposed through the candidate endpoint.
Job review remains on its existing occurrence view and API.

Verification: focused run **17 passed**, followed by expanded complete backend suite
**85 passed** with isolated PostgreSQL enabled (including grouping/correction and
fresh-session checks). Frontend production build and git diff --check passed.
Coverage includes aliases, repeated evidence, separate concepts/releases, unlinked
fallback, mixed/all-rejected statuses, correction save/reload, taxonomy replacement,
ownership/CV scope and unchanged Job responses/review updates.

No migration was added or applied for consolidation; repository and last isolated
verified head remain 0007. Developer data/runtime were untouched by implementation
tests. Subsequent user-reported deployed acceptance verified grouped occurrences,
individual evidence/review controls and persistence of two approved occurrences
alongside one pending occurrence. Existing full-package import evidence is reused:
importer behavior was not changed by consolidation.

## Taxonomy Matching Behavior

The current linker normalizes terms before comparison.

It does not currently expose a separate `normalized` match method.

Current deterministic match labels include:

- `exact_preferred`
- `exact_alternative`

These exact methods operate on normalized values.

Fuzzy matching is used when deterministic normalized label matching fails.

Stability Batch 5 retains preferred 1.00, alternative 0.98, fuzzy confidence,
the 0.95 auto-approval threshold and the top-five candidate limit. Multiple
matching labels on one release-scoped concept collapse to its strongest match.
Only a unique top-confidence concept may auto-approve; equal-confidence distinct
concepts remain pending, including across releases. Stable label/release/UUID
ordering determines display rank, not semantic superiority. The ambiguity check
precedes the candidate limit. Existing selections, approvals and audit events
were not rewritten; possible historical cleanup requires a separate authorized
inventory. Phase 5 remains incomplete pending human-labelled retrieval evaluation.

## Taxonomy Release Lifecycle

Current repository behavior:

- importing a new release for a taxonomy source deactivates older releases
  from that source
- reimporting the same taxonomy version deletes and recreates that stored
  version's concepts, labels, and occupations
- dependent mappings, taxonomy link candidates, and approved links may be
  removed by cascade during replacement
- mappings must be imported again after the taxonomy release is recreated
- extracted candidate/job terms must be relinked after replacement if their
  previous taxonomy links were removed

Imported releases preserve provenance metadata including:

- source filename
- SHA-256 checksum
- release date
- import time
- status
- `is_sample`

This behavior is important for reproducibility and must not be changed
silently.

## CV / Job Taxonomy-Link Lifecycle

For CV processing, extraction skills and terms are scoped to that CV; other
retained CVs and manual profile skills are not replaced. On reprocessing the
same CV, an occurrence is retained only when its complete extracted fields
(wording, type, section, evidence, method, confidence and offsets) match
uniquely. Its extraction decision, taxonomy candidates, selected link and
review history then remain intact. Changed or ambiguous duplicate occurrences
use the existing replacement lifecycle; no broader repeated-evidence identity
policy is implied. CV-scoped skill APIs also return profile-wide manual skills.
Candidate-edited text/type cannot yet be identified reliably after reprocessing
and may return to fresh extraction output; preserving corrections requires
explicit persisted provenance, and existing corrections cannot be classified
retroactively without guessing. Retained terms without suggestions may be
linked when an active taxonomy becomes available. An unchanged term may retain
a historical selection to an inactive release: retrieval ignores that canonical
link, and reprocessing does not silently rewrite the selection. Generating
replacement suggestions for inactive selections remains a separate decision.

Deleting a CV removes its extraction skills before its extracted terms are
deleted, so the existing SET NULL foreign key cannot leave those skills as
profile evidence. Cached prototype matches for that candidate are cleared so
the next read recomputes from retained skills. Its terms, link candidates and
approved links are removed; append-only taxonomy review events remain. Full
privacy erasure of audit history and cleanup of older orphan skills remain
separate decisions.

Job reprocessing/deletion continues to remove links for superseded job terms.
Phase 5 remains incomplete pending human-labelled retrieval evaluation.

Stability Batch 6 changes future extracted job-skill edits only: semantic
raw/normalized text or type corrections synchronize the extracted term and
remove that term's obsolete active taxonomy selection and suggestions.
Invalidation is removal, not a fabricated rejection or superseded human
choice; append-only review events remain. Evidence, requirement and review
status edits preserve a valid taxonomy selection, while every effective edit
stales current job embeddings transactionally. Relinking/review and reindexing
remain explicit. Historical developer records were not repaired. Phase 5
remains incomplete pending human-labelled retrieval evaluation.
Batch 6 verification used a disposable tmpfs PostgreSQL/pgvector container:
10 Batch 6 regressions passed; 81 affected job-skill, taxonomy, retrieval,
extraction and permission tests passed; and the complete PostgreSQL-enabled
backend suite passed 252 tests with 1 skip. The skipped gated real-model test
was not run because its model path was not configured for this run. An in-memory
stale-link mutation was caught by the new fresh-session regression, and
`git diff --check` passed. The disposable container was removed; all eight
pre-existing containers remained stopped. The developer database and normal
Compose project were not accessed, and no runtime deployment occurred.
Repository and isolated verified Alembic heads remain `0008_dense_retrieval`;
the developer database remains at its last independently observed
`0007_taxonomy_review_audit` state. Batch 6 is verified but uncommitted;
Phase 5 remains incomplete pending human-labelled retrieval evaluation.

## Historical Manual Local Verification Snapshot

The following results were observed earlier in the developer's local
PostgreSQL volume.

This snapshot predates the review consistency blocker above. The user subsequently
approved both REST APIs alternatives; only rank 2 was selected. Those developer
records were intentionally left untouched by implementation/tests for explicit UI
correction. This historical snapshot is not a claim about their current state;
subsequent user-reported workflow acceptance is recorded in the closure section.

They are NOT guaranteed repository state.

A fresh clone or database-volume reset will not contain these records until
the relevant development samples and test CV are loaded again.

Observed active development releases:

- ESCO `sample-1.0`
- ONET `sample-1.0`

Both were correctly identified as sample releases.

Observed O*NET occupations included:

- `15-1252.00` Software Developers
- `15-2051.00` Data Scientists

Observed candidate taxonomy mappings included:

FastAPI
→ FastAPI
→ `exact_preferred`
→ 1.0000
→ approved

Git
→ use version control software
→ `exact_alternative`
→ 0.9800
→ approved

Python
→ Python (computer programming)
→ `exact_alternative`
→ 0.9800
→ approved

SQL
→ SQL
→ `exact_preferred`
→ 1.0000
→ approved

Observed fuzzy candidates included:

REST APIs
→ develop REST APIs
→ 0.8847
→ rank 1
→ pending

REST APIs
→ FastAPI
→ 0.7050
→ rank 2
→ pending

These results demonstrate that uncertain mappings can remain ranked and
pending rather than being forced.

## Docker Sample Data Fix

Manual testing found that the backend container could not access:

/data/sample/esco_sample.json

Root cause:

The repository data directory was not mounted in the backend container.

Fixed in commit:

9c2340c Fix taxonomy sample data mount

Current backend Compose configuration includes:

volumes:
  - ./data:/data

## Current Taxonomy Permissions

Administrator/researcher-only operations include:

- taxonomy import
- manual linking/relinking operations
- mapping/link review
- administrative processing logs

Authenticated candidate users may currently use selected read-only taxonomy
APIs, including:

- taxonomy search
- concept details
- occupation details
- taxonomy version listing
- ESCO–O*NET mapping listing

The frontend Taxonomy administration page remains role-restricted.

Future agents must distinguish taxonomy management permissions from
authenticated read-only lookup permissions.

## Phase 4 Closure Acceptance (2026-10-02)

All required implementation and functional acceptance criteria are satisfied.
Evidence sources are distinguished: automated/full-package results are recorded in
the repository; deployed browser/runtime checks and fresh developer counts below
were supplied by the user. This documentation-only review did not rerun those checks
or inspect/change the developer database.

| Acceptance area | Evidence and outcome |
| --- | --- |
| Pinned ESCO/O*NET imports, relationships and fixtures | Isolated full-package reports, regression tests and successful browser imports |
| Transactional replacement, rollback, FK/uniqueness and upgrades | Isolated PostgreSQL verification; ESCO replacement evidence retained, O*NET 31.0 initial/replacement round trips passed |
| Backend/frontend | Latest complete suite 146 passed, none skipped; production build passed; updated backend/frontend successfully deployed per user |
| Administrator/researcher interface | Working in deployed browser per user |
| Candidate restrictions and intended reads | Administrative page redirect, authenticated read-only APIs and intended 403 responses verified per user |
| Taxonomy review consistency | Approval, rejection, replacement, superseded state, refresh persistence and history verified per user; selected/alternative rejection covered by regression tests |
| Candidate consolidation | Grouping by taxonomy identity, separate evidence/review controls and two approved/one pending occurrences persisted per user; edge cases and corrections covered by regression tests |
| Migration status | At Phase 4 closure, repository and isolated verified heads were 0007_taxonomy_review_audit; the developer head was last independently observed at 0007_taxonomy_review_audit through a read-only query on 2026-10-06 |

### Active developer releases

User-reported fresh database counts after deployed browser imports:

| Active release | Concepts | Occupation table rows | O*NET source records | Directed relationships |
| --- | ---: | ---: | ---: | ---: |
| O*NET 31.0 CSV | 4,022 | 1,016 | 1,120,006 | 20,262 |
| ESCO 1.2.1 English CSV | 18,237 | 0 (expected) | Not applicable | 156,336 |

ESCO occupations are taxonomy concepts; the separate occupations table is
O*NET-oriented. Sample releases remain stored but are not active official releases.
O*NET 29.0 TXT remains supported with historical evidence; this does not assert
it is imported or active in the developer database.

The ESCO browser import used a ZIP reconstructed from the unchanged supplied
directory. The original distribution ZIP checksum remains unavailable. Per-member
hashes and reconstructed-ZIP evidence do not authenticate the original distribution.
No other release/format support is implied by Phase 4 completion.

### Checkpoint hygiene

Functional closure is complete; the final Git checkpoint has not been created.
The working tree contains the accumulated Phase 4 implementation and documentation;
nothing was staged at closure review. The supplied O*NET ZIP and older pre-upgrade
dump are ignored. However, `esco-1.2.1-en.zip` and
`phase4-before-onet31-runtime-20261002-082407.dump` are untracked and NOT ignored.
Neither is staged or tracked. Exclude them from the checkpoint and add appropriate
ignore rules in a separately authorized repository-hygiene change. Do not use
`git add .` or `git add -A`. Exact checkpoint scope is in phase4-verification.md.

## Phase 5

Phase 5 — Dense Retrieval

Status: COMPLETE as a repository/methodology checkpoint. Implementation, pinned
offline-model execution, PostgreSQL retrieval verification and human-labelled
evaluation are accepted. The owner explicitly approved the run-specific
scoped-isolation exception (D033). Do not treat normal Compose deployment as
implied by this evidence. Phase 6 application implementation has not begun;
its accepted methodology checkpoint is recorded in Current Phase above.

The checkpoint histories below retain their original test counts and status
context. Empty embedding tables, pending judgments and incomplete status refer
to those earlier steps, not the accepted corpus evaluation at the end of this
section. That closure section is the source of truth for Phase 5 completion;
Current Phase above records the subsequent Phase 6 methodology checkpoint.

Phase 5 implementation scope:

- embedding abstraction
- Sentence Transformer model
- model/version metadata
- candidate/profile embeddings
- job embeddings
- pgvector/vector-store abstraction
- top-N semantic job retrieval
- semantic retrieval tests

The current implementation adds migration `0008_dense_retrieval`, separate
candidate/profile and job vectors, a resumable indexing CLI, and candidate-only
`GET /retrieval/jobs`. Exact cosine retrieval remains separate from
`/matches/recommendations`. There is no semantic taxonomy-linking change.
The new representation and provisioning contract is in phase5-dense-retrieval.md.
The developer database is now independently observed through authorized
read-only corpus queries at `0008_dense_retrieval`; no migration was run during
the template-v2 work. The repository head is `0008_dense_retrieval`.
Last successfully verified migration revision is `0008_dense_retrieval` in
isolated PostgreSQL. A populated `0007` schema was upgraded, downgraded and
re-upgraded there; extension, vector(384),
foreign keys, uniqueness, cascade and fresh-session cosine ranking passed.
Backend container startup now performs a read-only exact Alembic head-set check
before Uvicorn. It refuses mismatched or unreachable databases; it does not
apply migrations. The opt-in Compose `migrate` service runs `alembic upgrade head`
only when deliberately invoked with the `maintenance` profile. Ordinary Compose
startup does not run or depend on it. Historically the developer database was
not queried or modified during Stability Batch 3, and at that point its last
observed revision was `0007`; startup correctly refused that mismatch. Later
authorized deployment/corpus checks observed `0008`. Phase 5 remains incomplete.

Batch 3 verification after the static startup guard: focused migration-check
tests **12 passed** against isolated PostgreSQL; complete default backend suite
**178 passed, 33 skipped**; complete isolated PostgreSQL-enabled suite
**210 passed, 1 skipped**. Compose
configuration excluded `migrate` by default and included it with the maintenance
profile. Backend image build and disposable Docker checks passed: fresh and
behind/unknown revisions refused before serving, at-head health succeeded,
explicit migration and repeat migration succeeded, and failed startup left
the isolated revision/schema/sentinel unchanged. These prior disposable-runtime
results remain applicable because startup behavior was unchanged by the follow-up.
No normal Compose stack or
developer database was accessed or changed. A connection timeout remains a possible
future operational hardening measure; it was not implemented in Batch 3.

The pinned `intfloat/multilingual-e5-small` revision
`fd1525a9fd15316a2d503bf26ab031a61d056e98` was provisioned under the
ignored local `models/` directory and executed offline, including a
network-disabled container check. Real-model CLI indexing and exact pgvector
retrieval passed in a disposable schema of the isolated `phase5_verify`
PostgreSQL database. The populated `0007` fixture was upgraded to `0008`;
the schema was removed afterward. The gated real-model test passed. The
subsequent complete backend suite with isolated PostgreSQL and the offline
model enabled: **157 passed, 0 failed, 0 skipped**. Artifact hashes, checks,
fixture counts and measured timings are recorded in
`docs/verification/phase5-real-model.json` and summarized in
`docs/verification/phase5-real-model.md`. Earlier Docker image build and
`git diff --check` passed; no frontend files changed, so no frontend build was
needed for this historical verification. At that checkpoint the developer database remained at the
last independently observed `0007_taxonomy_review_audit` on 2026-10-06
(not queried or migrated in that step). No human-labelled relevance set had yet
been supplied. Later primary judgments and the coverage exception are recorded
below; real Recall@K/MRR evaluation is still **PENDING**. Phase 5 is not complete.

The Phase 5 human-labelled benchmark pack is implemented:
candidate/job JSONL validation, complete judgment-matrix validation, a
reproducible blind pair export, isolated-database ranking export, grade-2
Recall@5/10/20 and MRR calculation, optional separate grade-1 exploration,
and optional second-reviewer Cohen's kappa. See
`docs/phase5-evaluation-protocol.md`. Synthetic tests prove tooling behavior,
not retrieval quality. At the original tooling checkpoint there were **0**
eligible real candidate profiles, **0** eligible real jobs and **0** human
judgments; the target was 8 profiles, 30 jobs and 240 judgments. No developer
data was exported or judged in that tooling step. Focused benchmark tests: 7 passed. The complete
backend suite after this tooling change, with isolated PostgreSQL enabled:
**163 passed, 1 skipped** (the gated real-model test was not rerun in the host
Python environment without Torch). The separate pinned real-model verification
above remains valid. Do not declare Phase 5 complete.

The job-corpus contract now distinguishes `paraphrased` from
`verbatim_restricted` using `description_text`/`content_mode`. Legacy genuine
`description_paraphrase` records remain supported. Private verbatim job records
require complete PDF/source/hash provenance, `restricted_internal_use` and
literal `redistribution_allowed=false`; candidate consent/PII checks are
unchanged. Public recruiter/contact details are removed from local normalized
job text, with contact-free source-location audit records. Blind exports remain
private and carry explicit use restrictions (D029). Verification on 2026-11-03:
focused evaluation tests **40 passed**, including the private local corpus;
complete default backend suite **241 passed, 45 skipped** (44 PostgreSQL-gated
checks, including the real-model check, and the separately gated private-corpus
check, which passed in the focused run). `validate-benchmark` accepts
**8 candidates / 30 jobs / 240 expected pairs**, without judgments or metrics.
Six normalized job texts were contact-redacted; all 40 source PDF hashes and
frozen candidate files remain unchanged. No application/database access,
source-PDF edits, embeddings, rankings or judgments are involved.
Human-labelled evaluation remains pending and Phase 5 remains incomplete.

### Representation Template V2 (Historical Pre-Commit Verification)

`e5-job-profile-v1` remains explicitly callable/selectable with unchanged text
and hashes. `e5-job-profile-v2` is the default main-evaluation contract, fixed
before relevance judgments/rankings (D030). Candidate text is unchanged; its
source hash identifies the selected contract. Job v2 uses stored sections,
generic heading/condition/action cues and deterministic token reservations;
the pinned local tokenizer enforces 512 tokens including special tokens. It
does not alter source text, extraction, skills, reviews or taxonomy selections.
Full inputs and selected text are hashed. CLI/API/evaluation select the same
version; PostgreSQL uniqueness/query filters isolate both versions. No migration
is added, and existing v1 rows are not overwritten. Switching templates requires
explicit indexing of both sides, not merely changing the API parameter.

Repository and isolated verified migration heads remain `0008_dense_retrieval`.
The developer database was independently read at `0008_dense_retrieval` for the
authorized corpus checks; it was not migrated or modified during this work.
Earlier `0007` statements above describe historical observations, not this
current read-only observation. Production embedding tables remain empty.
Read-only corpus verification and test evidence are recorded in
`docs/verification/phase5-template-v2.json`; historical v1 real-model evidence
remains separate. No evaluation vectors, retrieval rankings or judgments have
been generated. Phase 5 remains incomplete.

Initial V2 verification: focused representation/retrieval/benchmark **63 passed, 1
skipped** (private corpus enabled); complete default backend **256 passed, 47
skipped**; isolated PostgreSQL host **300 passed, 3 skipped**; complete isolated
PostgreSQL with the offline pinned real model **302 passed, 1 skipped**. The
remaining private-corpus gate passed in the focused host run. Real-model
inference/retrieval used synthetic disposable records only. All 30 dry-run v2
texts are deterministic, at most 512 tokens (observed 506-508), with requirement
and duty source content retained. The initial J12 short preferred overlap was
subsequently identified as a classification defect, not token-budget truncation.
All 30 v1 hashes, candidate frozen text, developer rows and local
source files remain unchanged; production embeddings remain empty. Disposable
test resources were removed. No frontend change/build or migration was needed.

Accepted unreleased-v2 follow-up: desired-section aliases are preferred; only
clear whole-line optional wording may override an explicit heading. Mixed or
parenthetical/subordinate preferences retain the explicit section class and
source wording. J12 retains ten preferred units: seven complete units and three budget-clipped verbatim prefixes.
Its required-experience line remains required and complete at 75/75 characters.
The three prefixes contain only verbatim source text: expected token-budget
behavior, not invented or paraphrased text. No stored classifications/reviews
were changed. All selected units were checked against their source wording.
The 30 outputs remain deterministic and within 512 tokens; all v1 hashes and
frozen candidate inputs are unchanged. Regression coverage includes coexisting
template invalidation, oversize shrinking, exact-512 preservation and HEAD v1
goldens. All five requested in-memory mutations were caught without source edits.
Follow-up verification: focused/private corpus **77 passed, 3 skipped**; complete
default backend **270 passed, 51 skipped**; isolated PostgreSQL **315 passed, 6
skipped**; pinned offline tokenizer/model-load-only and persistence gates **36
passed, 0 skipped**. The existing real-vector gate was not rerun under this
turn's no-encode/no-index boundary; historical real-model evidence remains valid.
No deployment, normal-stack rebuild, developer-data mutation or migration was
performed. Phase 5 remains incomplete pending human-labelled evaluation.

### Explicit Grade-2 Coverage Policy

The private frozen corpus now has 8 candidates, 30 jobs and 240 completed
primary judgments. The project owner accepted one zero-grade-2 query as a
**post-judgment corpus-coverage deviation**, not a retrieval result or a
preregistered policy. Grade-2 query coverage is **7/8**: 8 total, 7 evaluable,
1 excluded/undefined, with future aggregate binary Recall@K/MRR denominator
**7**. Excluded aliases/reasons must accompany eventual results. No grade 1
is promoted to grade 2; the candidate remains available for separate declared
graded/descriptive analysis. Single-rater subjectivity remains a limitation;
there is no inter-rater reliability estimate (D031).

`validate-benchmark` and `evaluate` accept optional `--evaluation-policy PATH`.
Without it, zero-grade-2 queries still fail. The strict versioned schema binds
the exact candidate/job/judgment bytes and every record's freeze identity/hash,
requires a reason/date/methodology and explicit undefined/exclusion/retention
treatment, and rejects unknown, duplicate, positive-covered or undeclared
exclusions. No alias is hard-coded. Excluded per-query binary metrics are
`null`; aggregates omit them and report coverage/denominator prominently.
Optional grade-1-or-2 exploration retains its separate denominator.
The deliberately incomplete policy template and protocol document the input;
a narrative decision is not silently treated as a valid machine policy.
Policy v1 requires literal `post_judgment_protocol_deviation=true`; false,
null, missing and non-boolean declarations fail. Validation and evaluation
limitations state: "This coverage exception was adopted after the relevance judgments were collected."
No separate source-decision hash is accepted or reported. The policy file's own
SHA-256 and existing corpus/export hashes remain authoritative; older policies
with the removed extra field must be regenerated.

Read-only validation of the real completed matrix confirmed strict rejection
without policy and acceptance of **240 pairs / 7/8 coverage** with a temporary
policy explicitly derived from the preserved owner decision. The temporary
policy was removed. CSV/JSONL exports, export-integrity record, original failed
validation and historical decision retained their recorded SHA-256 hashes;
both frozen corpus files were unchanged. This was validation only, not ranking
or metric execution. Evaluator aggregation tests use injected synthetic results.
No application/developer database access, indexing, vectors, real rankings,
metrics, migrations, frontend changes or deployment occurred. Phase 5 remains
incomplete pending retrieval-quality evaluation.

Verification on 2026-11-04: focused policy/benchmark tests **75 passed,
1 skipped** (private-corpus gate unset); complete default backend suite
**306 passed, 51 skipped** (PostgreSQL, pinned tokenizer/real-model and private
corpus environment gates unset). The separate read-only real-matrix check above
passed. `git diff --check` passed, including the new untracked source/template
files. No frontend build is necessary. Repository Alembic head remains
`0008_dense_retrieval`; developer migration state was not queried in this work.

Acceptance follow-up on 2026-11-05: focused policy/benchmark tests **85 passed,
1 skipped**; complete default backend suite **316 passed, 51 skipped**, with
the same environment gates unset. New regressions cover literal-true-only
declaration, explicit post-judgment wording in validation/evaluation output,
and rejection/non-reporting of the removed extra hash field. Read-only real
matrix validation still reports **8 total / 7 evaluable / 1 excluded, coverage
7/8, binary denominator 7**; strict validation without policy still fails.
All completed judgments and frozen corpus/historical records remain unchanged.
No application database access or real metric/ranking execution occurred.
`git diff --check` passed, including new untracked files. Work is uncommitted.

### Accepted Frozen Evaluation and Closure Review

Independent verdict: **ACCEPT - PHASE 5 EVALUATION RESULTS**.
The benchmark's source commit is `d80e2c9`, contract `e5-job-profile-v2`,
model `intfloat/multilingual-e5-small` at immutable revision
`fd1525a9fd15316a2d503bf26ab031a61d056e98`.
See [the concise verification/result report](verification/phase5-real-corpus-results.md)
for exact hashes, fractions, method definitions and the requirements matrix.

The frozen corpus is 8 candidates by 30 jobs, with all 240 human judgments:
167 grade 0, 54 grade 1 and 19 grade 2. Primary grade-2 coverage is **7/8**:
8 total, 7 evaluable, 1 excluded/undefined and binary macro denominator **7**.
`candidate_831967b28fd6` has no clearly relevant job identified in the corpus;
its primary metrics are **null/undefined, not zero**. No labels were changed.
This coverage exception was adopted after the relevance judgments were collected.

| Primary Metric | Exact Fraction | Macro Value |
| --- | --- | ---: |
| Recall@5 | 37/84 | 0.440476 |
| Recall@10 | 53/84 | 0.630952 |
| Recall@20 | 5/7 | 0.714286 |
| MRR | 1261/1925 | 0.655065 |

MRR indicates that a clearly relevant result often appears relatively early,
but performance is uneven. Recall increases with K. About **28.6% remains
outside top 20 on the macro measure**, not 28.6% of all positive pairs.
Two of the 19 positive pairs lie outside 20, each the sole positive for a
different query. Grade-1-or-2 exploration is separate, with denominator 8.

The frozen indexing evidence records exactly 8 ready/current candidate and 30
job vectors, explicit v2 and pinned artifacts, with 38 encode calls. Job inputs
are 503-508 tokens. Two independent read-only service runs produced identical
240-row rankings. All 29 database table fingerprints were unchanged during
ranking; legacy matches remained 13/13 with identical fingerprint and evaluation
matches 0/0. The offline committed evaluator ran twice with byte-identical
normalized results; independent exact-fraction verification agreed within 1e-12.
The accepted evaluation ID is `evaluation_v2_4ad60a9a219015141927c755`.
Its labels, policy, ranking and metric files remain immutable. A new detailed
interpretation is private mode-0600 material, not part of the metric manifest.

All recorded implementation/model/PostgreSQL/human-evaluation gates have
evidence. The owner explicitly accepted the authorized scoped-isolation
exception for closure on 2026-11-08 (D033). The earlier protocol specified a
physically isolated benchmark-only database; the actual corpus run used a
shared developer database with only the frozen 8/30 entities embedded. Other
profiles/jobs had no embeddings; all 13 legacy matches were excluded from
ranking inputs and preserved. All 29 table fingerprints remained unchanged
during ranking. This is verified retrieval-universe isolation, not physical
database isolation. Isolated PostgreSQL implementation/migration verification
remains separate. Shared execution was authorized before indexing; acceptance
of the original checklist substitution is recorded at closure after evaluation.
No results, labels or execution are retroactively changed or rerun. Phase 5 is
complete with these methodological limitations; no required work remains for
this repository/methodology checkpoint.

Limitations: 8 candidates and 30 curated English jobs; only 7 evaluable binary
queries; one candidate has no grade-2 job; post-judgment exclusion; a single
primary rater and **no inter-rater reliability estimate**; manually reviewed
and augmented candidate profiles; no end-to-end extraction-quality measurement;
restricted internal employer material. Do not generalize these results as
production hiring accuracy or confuse them with final Phase 6 scores.

Repository migration head, isolated verified head and last observed developer
head are all `0008_dense_retrieval`; the developer head was not queried in this
documentation step. Current-source one-off runners do not establish deployment
of the latest image to normal Compose. No runtime deployment was performed.

At the Phase 5 closure checkpoint, Phase 6 had not started. Its planned
recommendations were explainable reviewed-skill
coverage, required/preferred distinctions, gaps, qualifications and seniority.
It must not retroactively tune or replace the frozen Phase 5 baseline (D032).

Documentation/interpretation verification on 2026-11-08: exact primary fractions,
all 19 positive ranks and outside-top-K counts were checked against the frozen
results. Corpus, label, ranking and evaluation manifests pass; all 56
pre-existing frozen files remain unchanged. Tracked-document privacy scans
found no restricted summaries/descriptions, private rationales or database
identifiers. Focused benchmark/policy tests: **85 passed, 1 skipped** (private
corpus gate unset; direct frozen-file checks passed separately).
`git diff --check` passed, including the new verification report. No frontend
build, migration, application database access or runtime operation was needed.
The documentation changes remain uncommitted for review.
The approved closure follow-up changes documentation only; frozen evidence
remains unchanged. No latest-image deployment or Phase 6 work was performed.

Do not implement the final Phase 6 weighted scoring model as part of Phase 5.

Expected sequence:

Candidate profile
→ embedding
→ vector retrieval
→ top-N jobs
→ Phase 6 detailed matching later
