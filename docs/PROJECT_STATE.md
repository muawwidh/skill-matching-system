# Project State

Last updated: 2026-09-30

## Repository

Main branch:

`main`

Last verified code checkpoint before agent-context documentation:

`9c2340c Fix taxonomy sample data mount`

Phase 4 implementation checkpoint:

`24dd9a7 Complete phase 4 taxonomy integration`

Initial Git baseline:

`cf40546 Establish phases 1-3 and matching baseline`

## Current Phase

Phase 4 — Taxonomy Integration

Implementation status:

CORE IMPLEMENTATION WORKING / COMPLETION PENDING

Current status:

FINAL IMPLEMENTATION AND MANUAL VERIFICATION

Next planned phase:

Phase 5 — Dense Retrieval

Do not begin Phase 5 until the remaining Phase 4 implementation and
acceptance checks are resolved unless explicitly instructed.

## Important Development History

After Phase 3, an early candidate-job matching implementation was built
and temporarily referred to as Phase 4.

The original requirements were subsequently rechecked.

The official Phase 4 is Taxonomy Integration.

Therefore the repository currently contains:

- completed Phase 1
- completed Phase 2
- completed Phase 3
- implemented Phase 4 taxonomy integration
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

Candidate-facing normalized skills should ultimately be deduplicated.

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

Migration:

`0005_taxonomy_integration`

Status:

CORE IMPLEMENTATION WORKING / COMPLETION PENDING

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

Schema exists but functionality is not yet complete for:

- taxonomy relationships

The database model/migration includes relationship storage, but the current
implementation does not yet provide complete relationship import, service,
repository, API, sample-data, or test coverage.

### Official taxonomy import limitation

The current importer accepts a project-defined flattened JSON/CSV/TSV/TXT
format.

It does NOT yet constitute complete native ingestion of official ESCO or
O*NET release packages.

The current implementation does not yet fully ingest all master-plan data
such as:

- ESCO relationship datasets
- O*NET tasks
- O*NET knowledge
- O*NET abilities
- O*NET work activities
- O*NET tools/technology
- O*NET education/experience datasets

Only the bundled sample import path has been verified end-to-end.

Therefore official taxonomy ingestion remains an important Phase 4
completion item.

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

Not yet verified with representative fixtures:

- CSV taxonomy import
- TSV taxonomy import
- TXT taxonomy import
- native official ESCO release format
- native official O*NET release format

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

## Manual Local Verification Snapshot

The following results were observed in the developer's current local
PostgreSQL volume.

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

## Remaining Phase 4 Work and Acceptance Checks

Before Phase 4 is marked fully COMPLETE:

### Implementation gaps

1. determine and implement the required native official ESCO import path
2. determine and implement the required native official O*NET import path
3. implement ESCO taxonomy relationship ingestion and corresponding
   persistence/tests as required by the master plan
4. add corresponding tests using representative official-format fixtures

### Manual workflow verification

5. verify researcher/admin approval of a pending taxonomy candidate
6. verify researcher/admin rejection of an incorrect taxonomy candidate
7. verify review decisions persist in PostgreSQL
8. verify ordinary candidate cannot perform taxonomy management operations
9. verify restricted management endpoints return 403 to candidates
10. verify intended authenticated read-only taxonomy endpoints remain
    accessible where designed
11. verify candidate-facing normalized skills do not unnecessarily display
    repeated extraction occurrences

After these are resolved:

- update this document
- run the complete backend test suite
- run the frontend production build
- verify Docker
- verify migration state
- create a Phase 4 completion Git checkpoint/tag

## Next Phase

Phase 5 — Dense Retrieval

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