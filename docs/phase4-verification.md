# Phase 4 verification

Phase 4 is COMPLETE as of 2026-10-02, based on recorded automated/full-package
evidence and user-reported deployed browser/runtime acceptance. Phase 5 Dense
Retrieval is next but NOT STARTED. Final scoring remains out of scope.

## Closure evidence (2026-10-02)

- Repository head: `0007_taxonomy_review_audit`.
- Isolated PostgreSQL verified head: `0007_taxonomy_review_audit`.
- Developer database head: `0007_taxonomy_review_audit`, reported by the user;
  not independently queried in this documentation-only closure review.
- Latest complete backend suite: 146 passed, none skipped, PostgreSQL enabled.
  Frontend production build and diff checks passed. These are retained results,
  not a claim that tests/build were rerun during the documentation review.
- User reports successful deployment of updated backend/frontend, functioning
  administrator/researcher taxonomy UI, candidate page redirects, intended
  authenticated read-only API access and restricted-endpoint 403 responses.
- User verified approval/rejection/replacement, superseded state, persistence
  after refresh and review history. Candidate groups retain occurrence-level
  evidence and controls; two approved occurrences and one pending occurrence
  persisted separately. Automated edge-case coverage complements this acceptance.
- Browser-imported active O*NET 31.0: 4,022 concepts, 1,016 occupations,
  1,120,006 source records, 20,262 directed relationships (user-reported fresh counts).
- Browser-imported active ESCO 1.2.1 English: 18,237 concepts and 156,336 directed
  relationships (user-reported fresh counts). Zero separate occupation-table rows
  is expected: ESCO occupations are taxonomy concepts.
- Sample releases remain stored, but are no longer the active official releases.
- O*NET 31.0 full import and replacement verified every source field and all dataset
  counts in fresh isolated sessions. Report: `verification/onet-31.0.json`.
  ESCO full-package import/replacement evidence and O*NET 29.0 TXT regression
  support/evidence remain valid; their original reports are unchanged.
- ESCO browser import used a ZIP reconstructed from the unchanged supplied
  directory. Its original distribution ZIP checksum remains UNAVAILABLE; no
  original-ZIP hash or cryptographic release authentication is claimed.

All required functional acceptance is satisfied. The Git checkpoint remains to be
created, with the archive/dump exclusion warning below. No application, database,
dataset, migration, embedding, retrieval or scoring change was made at closure.

## Historical outcome summary (2026-10-01, before closure)

The statuses and revisions in this historical section describe the initial native
package verification, not the current runtime. The closure evidence above supersedes
its pending acceptance and developer-revision notes.

- Files changed: taxonomy package adapter, model/migration, repository, service,
  API schemas/routes, verification CLI, native fixtures and tests; frontend ZIP
  selection/version hints; Nginx import limits; README and project documentation.
- Migration added: 0006_official_taxonomy. Repository head and last isolated-PG
  verified revision are 0006; developer database remains 0005.
- Full backend suite: 56 passed (50 non-PostgreSQL tests and 6 PostgreSQL tests).
  Existing dependency deprecation warnings remain; none failed tests.
- Frontend production build: passed (TypeScript and Vite).
- ESCO full input: 174,598 records; 18,237 concepts and 156,336 directed
  relationships stored, with 25 timestamp-only duplicate concept rows preserved
  in metadata. All dataset counts reconcile; no unresolved references.
- O*NET full input: 628,682 source records stored across 17 ingested datasets,
  plus 1,016 occupations and 1,224 concepts. All dataset counts reconcile;
  no unresolved references. Optional title/job-zone files were ingested.
- Full-size same-version replacement reruns passed for both packages.
- Docker: backend image built; isolated API health, registration and authenticated
  taxonomy version reads passed. Compose configuration and Nginx syntax passed.
  Existing application containers were not upgraded; their database was untouched.
- Outstanding: original ESCO distribution ZIP checksum unavailable; release
  identity relies on the user-supplied directory, not a signed manifest. Final
  browser acceptance and normalized candidate skill deduplication remain pending.
- No Phase 5, embeddings, vector retrieval, or final Phase 6 scoring was added.

## Historical database isolation and migrations

Verification uses PostgreSQL 16 in a separate container named
skillgap-phase4-verification, database phase4_verify, host port 55434.
Tests allocate and clean up unique schemas. The developer database is untouched.

- Repository migration head: `0006_official_taxonomy`.
- Last successfully verified revision: `0006_official_taxonomy`, isolated PostgreSQL.
- Developer Compose database: read-only query returned `0005_taxonomy_integration`.
  The new migration was NOT applied there.

Tests seed real 0005 tables using reflection, including concepts, labels,
relationships, occupations, mappings and human-reviewed links. Upgrade to 0006,
downgrade (exact row comparison) and re-upgrade pass. Failure injection after
concept, occupation and structured-record writes verifies whole-database rollback
from fresh connections. Successful same-version replacement and FK/uniqueness
constraints are tested separately. Approval and rejection persist across sessions.

## Full packages

Machine-readable evidence: `verification/esco-1.2.1-en.json` and
`verification/onet-29.0.json`. Reports include contract/version, SHA-256, member
hashes, input/inserted/merged counts, database counts, skipped files, unresolved
references, relationship checks, database revision/version, examples and duration.

ESCO input is the user's complete root-folder English CSV dataset, v1.2.1.
Its 19 filenames and headers were inspected. There is no embedded release-version
manifest: version is declared by the user/folder, with v1.2.1 structure corroboration
(relationship labels, occupation naceCode and dictionary). No cryptographic
authentication of the release is claimed.

The original download ZIP was not supplied, so its checksum is UNAVAILABLE.
The report checksum identifies a deterministic ZIP reconstructed from unchanged
directory bytes with fixed 1980 timestamps. It is NOT the original download ZIP
checksum. Per-file hashes identify the supplied dataset independently of packing.
The previously investigated v1.2.0 archive is not a supported contract.

O*NET is the full official 29.0 TXT ZIP downloaded from:
https://www.onetcenter.org/dl_files/database/db_29_0_text.zip

Fixtures derive from these inputs. Attribution is in
backend/tests/fixtures/taxonomy/README.md. Tests never download external data.

## Repeating verification

From backend, set PHASE4_TEST_DATABASE_URL to the isolated PostgreSQL URL and run:

```sh
.venv/bin/python -m pytest -q
```

Without that URL, PostgreSQL tests explicitly skip as UNVERIFIED, not passed.
For full packages set DATABASE_URL to the same isolated database and run:

```sh
.venv/bin/python -m app.scripts.verify_taxonomy_package ESCO 1.2.1 \
  '../ESCO dataset - v1.2.1 - classification - en - csv' \
  --provenance 'User-supplied English CSV directory; reconstructed ZIP' \
  --output ../docs/verification/esco-1.2.1-en.json
.venv/bin/python -m app.scripts.verify_taxonomy_package ONET 29.0 /path/to/db_29_0_text.zip \
  --provenance 'https://www.onetcenter.org/dl_files/database/db_29_0_text.zip' \
  --output ../docs/verification/onet-29.0.json
```

The verifier refuses databases not named phase4_verify. Use a separate container;
the name guard is not a substitute for actual isolation. It applies migrations,
imports transactionally, checks database counts in a fresh session and emits
success evidence only after assertions pass.

## Checkpoint scope and exclusions

At closure review nothing is staged. `db_31_0_csv.zip`, the supplied ESCO directory
and `phase4-before-upgrade-20261001-180512.dump` match ignore rules. Two unrelated
local artifacts do NOT: `esco-1.2.1-en.zip` and
`phase4-before-onet31-runtime-20261002-082407.dump`. Both are untracked, not staged.
No ZIP or dump is tracked. Do not broadly stage the working tree. This documentation
request does not authorize editing .gitignore; arrange a separate hygiene update
for those two exclusions before the final checkpoint. No commit/tag was created.

Recommended checkpoint: the accumulated verified Phase 4 changes since 6613edc,
including native adapters/migrations, review consistency, candidate consolidation,
tests/fixtures, package reports, deployment import configuration and documentation.
No unrelated source changes were identified in the current change inventory.
Use this explicit path allowlist (after reviewing the separate ignore-rule fix):

```sh
git add -- .gitignore README.md \
  backend/app/api/routes/cvs.py backend/app/api/routes/taxonomy.py \
  backend/app/db/migrations/env.py \
  backend/app/db/migrations/versions/0006_official_taxonomy.py \
  backend/app/db/migrations/versions/0007_taxonomy_review_audit.py \
  backend/app/db/models/taxonomy.py \
  backend/app/repositories/document_repository.py backend/app/repositories/taxonomy_repository.py \
  backend/app/schemas/documents.py backend/app/schemas/taxonomy.py \
  backend/app/services/skill_service.py backend/app/services/taxonomy_service.py \
  backend/app/scripts/verify_taxonomy_package.py backend/app/scripts/verify_onet31.py \
  backend/app/taxonomy/packages.py backend/app/taxonomy/onet_31.py \
  backend/app/taxonomy/onet_31_manifest.json \
  backend/tests/test_skill_extraction.py backend/tests/test_candidate_skill_groups.py \
  backend/tests/test_official_packages.py backend/tests/test_onet31.py \
  backend/tests/test_taxonomy_postgres.py backend/tests/test_taxonomy_review.py \
  backend/tests/fixtures/taxonomy backend/tests/fixtures/onet31 \
  frontend/src/api/documents.ts frontend/src/api/taxonomy.ts \
  frontend/src/components/SkillReviewPanel.tsx frontend/src/components/CandidateSkillGroups.tsx \
  frontend/src/components/TaxonomyReviewPanel.tsx frontend/src/pages/TaxonomyPage.tsx \
  frontend/src/types/documents.ts frontend/src/types/taxonomy.ts nginx/default.conf \
  docs/DECISIONS.md docs/MASTER_PLAN.md docs/PROJECT_STATE.md \
  docs/taxonomy-integration.md docs/onet-31-contract.md docs/phase4-verification.md \
  docs/verification/esco-1.2.1-en.json docs/verification/onet-29.0.json \
  docs/verification/onet-31.0.json
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

Confirm no dataset archives, database dumps, .env, private CVs or generated runtime
data appear. Suggested commit message: `Complete verified Phase 4 taxonomy integration`.
This allowlist includes small attributed fixtures, not full distribution packages.
