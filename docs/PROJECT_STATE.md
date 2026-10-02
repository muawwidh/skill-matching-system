# Project State

Last updated: 2026-10-02

## Repository

Main branch:

`main`

Last verified code checkpoint before agent-context documentation:

`9c2340c Fix taxonomy sample data mount`

Earlier Phase 4 implementation checkpoint (not the final closure checkpoint):

`24dd9a7 Complete phase 4 taxonomy integration`

Initial Git baseline:

`cf40546 Establish phases 1-3 and matching baseline`

## Current Phase

Phase 4 — Taxonomy Integration

Implementation status:

COMPLETE

Current status:

PHASE 4 CLOSED ON 2026-10-02; FINAL GIT CHECKPOINT PENDING

Next planned phase:

Phase 5 — Dense Retrieval (NOT STARTED)

Phase 4 closure combines repository test/package evidence with user-reported
deployed browser/runtime acceptance. Phase 5 requires a separate instruction;
no embeddings, dense retrieval or scoring changes were introduced at closure.

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

Migration status (three distinct states):

- Repository migration head: `0007_taxonomy_review_audit`.
- Last successfully verified revision: `0007_taxonomy_review_audit`, isolated PostgreSQL 16,
  including populated 0005 upgrade and preservation of existing reviews from 0006.
- Developer local Compose database head: `0007_taxonomy_review_audit`, user-reported
  deployed runtime evidence on 2026-10-02; not queried or changed by this documentation review.

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
- automatic approval of strong deterministic matches
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

When a CV or job is reprocessed or deleted, old taxonomy-link candidates and
approved links associated with superseded extracted terms are removed before
replacement processing occurs.

This prevents stale taxonomy links from surviving document reprocessing.

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
| Migration status | Repository, isolated verified and user-reported developer heads all 0007_taxonomy_review_audit |

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

## Next Phase

Phase 5 — Dense Retrieval

Status: NOT STARTED. Await a separate explicit implementation request.

Phase 5 should implement:

- embedding abstraction
- Sentence Transformer model
- model/version metadata
- candidate/profile embeddings
- job embeddings
- pgvector/vector-store abstraction
- top-N semantic job retrieval
- semantic retrieval tests

Do not implement the final Phase 6 weighted scoring model as part of Phase 5.

Expected sequence:

Candidate profile
→ embedding
→ vector retrieval
→ top-N jobs
→ Phase 6 detailed matching later
