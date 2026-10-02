# Taxonomy integration

Phase 4 is COMPLETE (2026-10-02). Automated/full-package evidence plus user-reported
deployed browser/runtime acceptance is recorded in phase4-verification.md. Repository,
isolated PostgreSQL verified and user-reported developer migration heads are all
`0007_taxonomy_review_audit`. Phase 5 Dense Retrieval is next, not started.

Active developer releases after browser imports (user-reported fresh counts):
O*NET 31.0 CSV has 4,022 concepts, 1,016 occupations, 1,120,006 source records and
20,262 directed relationships; ESCO 1.2.1 English has 18,237 concepts and 156,336
directed relationships. ESCO occupations are concepts, so zero rows in the separate
O*NET-oriented occupations table is expected. Samples remain stored but inactive.
The ESCO browser ZIP was reconstructed from the unchanged supplied directory;
the original distribution ZIP checksum is unavailable. Support remains pinned below.

## Review selection consistency

Migration `0007_taxonomy_review_audit` adds review events without changing existing
selections. Admin/researcher users can revisit terms through Taxonomy review's
Pending, Selected and All views. Pending excludes terms with a selected link;
Selected and All retain their alternatives. Search supports an extracted term UUID.

`GET /taxonomy/reviews` accepts state, q, limit and offset. Each group includes the
authoritative selection, selection token, all alternatives and an inconsistency flag.
`GET /taxonomy/reviews/{term_source}/{term_id}/history` returns paginated audit events.
Both endpoints are restricted to administrator/researcher users.

The existing `PUT /taxonomy/link/{candidate_id}/approve` accepts approved/rejected
actions. Replacing an existing selection requires `replace_selection: true` and
`expected_selection_token` from the current group; missing confirmation or a stale
token produces 409. The UI confirms replacement and selected-link rejection.
Replaced approvals become superseded (not incorrect). Rejection removes a link only
when that candidate is selected. Changes and audit snapshots are atomic; unchanged
repeated actions do not add events. Existing inconsistent rows are only reconciled
when explicitly reviewed, never by viewing them or running the migration.

To correct the reported REST APIs selection after deploying this update, open
Selected or All, search `0a1fe559-2a20-4f89-a3e7-c2be202db9a5`, and inspect Current
selection. Choose Replace selection on rank 1 (develop REST APIs), then Confirm
replacement. Rank 2 becomes superseded. If rank 2 is also semantically incorrect,
explicitly Reject that alternative afterward. Reload and inspect Review history.
These remain supported correction steps. Review workflow acceptance was subsequently
reported by the user; the implementation/tests did not silently repair developer rows.

Phase 4 stores releases locally. No live taxonomy requests occur during matching.
The exact official-format contracts implemented and full-package tested are:

- ESCO **1.2.1**, classification, **English only**, native CSV ZIP.
- O*NET **29.0**, native tab-delimited TXT ZIP.
- O*NET **31.0**, complete inspected CSV ZIP, separate versioned adapter.

See `phase4-verification.md` and `verification/*.json` for evidence and provenance.
No ESCO 1.2.0, other O*NET version, O*NET 31.0 TXT, RDF, ODS or Excel compatibility
is claimed. Version is declared, not authenticated. O*NET 29.0 Read Me.txt, if supplied,
must identify 29.0; 31.0 CSV requires its Read Me.txt and matching release declaration.
The supplied ESCO directory has no release-version manifest.

Existing flattened JSON/CSV/TSV/TXT and bundled sample-1.0 remain development/
interchange adapters, NOT native official release-package support.

## Package contract

Use administrator/researcher multipart endpoints `POST /taxonomy/import/esco` or
`/taxonomy/import/onet`, with file, exact version (1.2.1, 29.0 or 31.0), and optional
release_date. Submit the whole ZIP, not individual supporting native tables.

The complete 31.0 CSV manifest and identity rules are in [onet-31-contract.md](onet-31-contract.md)
and `backend/app/taxonomy/onet_31_manifest.json`; all 45 CSV files plus Read Me.txt
are required. The TXT filenames/optional rules below apply to 29.0 only.

Exact filenames and case matter. A surrounding directory is allowed; ambiguous
duplicate basenames are rejected. Required files/headers are enumerated below
and enforced in app/taxonomy/packages.py. Additional columns remain in source
metadata. UTF-8 with optional BOM, quoted CSV and multiline fields are supported.

All eight listed ESCO files are required. O*NET files are required except Alternate
Titles.txt, Job Zones.txt and Job Zone Reference.txt. Supplying Job Zones requires
Job Zone Reference. All three optional ingestion implementations have tests.
Task Categories.txt is required to interpret Task Ratings categories.

Unknown files are not ingested and appear in skipped_files; their bytes still
count toward archive limits and their hashes are recorded. Missing optional files
are reported separately. Missing required files/headers, malformed rows, unsupported
versions, invalid numbers, out-of-range ratings, unresolved references and
conflicting duplicate identities fail the whole import.

## Archive safety

- Maximum uploaded file: 128 MiB, including legacy imports.
- Maximum uncompressed archive: 512 MiB.
- Maximum uncompressed member: 128 MiB.
- Maximum archive entries, including directories: 128.

Both ZIP-declared and actual decompressed bytes are checked. Reading uses bounded
chunks, not filesystem extraction. Traversal/absolute paths, symlinks, encrypted
archives, duplicate basenames and corrupt ZIPs fail validation. Nginx permits
129 MiB for multipart framing only on taxonomy import paths; the file limit
remains 128 MiB in the API. Unknown members also undergo archive checks.

## Persistence and semantics

ESCO URIs are unchanged. Broader links point child to parent; occupation-skill
links point occupation to skill; skill-skill links preserve originalSkillUri to
relatedSkillUri. Essential, optional and broader remain distinct relationship
types. Original rows retain skill types and endpoint labels. Composite foreign
keys enforce both endpoints belong to the relationship release.

The supplied v1.2.1 files contain 21 repeated skill URIs and 4 repeated occupation
URIs differing only in modifiedDate. One concept is stored per URI; every original
row is retained in metadata_json.source_rows. merged_duplicate_rows explicitly
accounts for this. Differences in any other field fail validation. Input count
equals inserted count plus merged duplicate count.

O*NET occupations and searchable skill/knowledge/ability/work-activity elements
use existing tables. Every ingested source row also persists in onet_data_records,
keyed by release/dataset/identity, with occupation code, element ID, task ID,
scale ID, category, exact numeric value and full original row. Scale/category
definitions persist as release-scoped reference records. Occupation references
have composite foreign keys; element/scale/task/category/job-zone references are
validated within the incoming package. Source data preserves missing/nonapplicable
values, statistics, suppression flags, dates and domain source.

## Transactions and replacement

Validation precedes writes. A source-scoped PostgreSQL advisory transaction lock
serializes same-source imports. Replacement, inserts, deactivation and activation
commit together. Any exception rolls everything back, including failures after
cascade deletion and partial writes. Repository helpers never commit.

Successful same-version replacement retains the documented lifecycle: concepts,
labels, relationships, occupations and structured data are recreated; dependent
mappings and reviewed taxonomy links may cascade away. Reimport mappings and
relink extracted terms afterwards. New versions retain older versions as inactive.
This is NOT automatic migration of human review decisions.

## Read APIs and reports

Authenticated users retain search/details/versions/mappings access. Added
paginated endpoints (limit 1-500, offset >= 0):

- GET /taxonomy/concepts/{id}/relationships
- GET /taxonomy/occupations/{id}/data

Version responses include checksum and persisted import report. Import reports
contain the contract, member hashes, per-dataset input/inserted/merged counts,
skipped files, missing optional files, unresolved references and relationship
resolution count. The full-package verifier separately checks actual database
counts in a fresh session. Fixtures alone do not establish official package support.

Linking is unchanged: normalized preferred (1.0), alternative (0.98), then
RapidFuzz (threshold 0.70, scaled by 0.94), top five candidates. Only the top
candidate >= 0.95 auto-approves. No embeddings or final scoring changes.

## Required headers

Every listed column must be present, including columns whose source values may
be empty or n/a. Field order is not significant.

### ESCO

- `skills_en.csv`: `conceptType`, `conceptUri`, `skillType`, `reuseLevel`, `preferredLabel`, `altLabels`, `hiddenLabels`, `status`, `modifiedDate`, `scopeNote`, `definition`, `inScheme`, `description`.
- `occupations_en.csv`: `conceptType`, `conceptUri`, `iscoGroup`, `preferredLabel`, `altLabels`, `hiddenLabels`, `status`, `modifiedDate`, `regulatedProfessionNote`, `scopeNote`, `definition`, `inScheme`, `description`, `code`, `naceCode`.
- `skillGroups_en.csv`: `conceptType`, `conceptUri`, `preferredLabel`, `altLabels`, `hiddenLabels`, `status`, `modifiedDate`, `scopeNote`, `inScheme`, `description`, `code`.
- `ISCOGroups_en.csv`: `conceptType`, `conceptUri`, `code`, `preferredLabel`, `status`, `altLabels`, `inScheme`, `description`.
- `broaderRelationsSkillPillar_en.csv`: `conceptType`, `conceptUri`, `conceptLabel`, `broaderType`, `broaderUri`, `broaderLabel`.
- `broaderRelationsOccPillar_en.csv`: `conceptType`, `conceptUri`, `conceptLabel`, `broaderType`, `broaderUri`, `broaderLabel`.
- `occupationSkillRelations_en.csv`: `occupationUri`, `occupationLabel`, `relationType`, `skillType`, `skillUri`, `skillLabel`.
- `skillSkillRelations_en.csv`: `originalSkillUri`, `originalSkillType`, `relationType`, `relatedSkillType`, `relatedSkillUri`.

### ONET 29.0 TXT

- `Occupation Data.txt`: `O*NET-SOC Code`, `Title`, `Description`.
- `Content Model Reference.txt`: `Element ID`, `Element Name`, `Description`.
- `Scales Reference.txt`: `Scale ID`, `Scale Name`, `Minimum`, `Maximum`.
- `Skills.txt`: `O*NET-SOC Code`, `Element ID`, `Element Name`, `Scale ID`, `Data Value`, `N`, `Standard Error`, `Lower CI Bound`, `Upper CI Bound`, `Recommend Suppress`, `Not Relevant`, `Date`, `Domain Source`.
- `Knowledge.txt`: `O*NET-SOC Code`, `Element ID`, `Element Name`, `Scale ID`, `Data Value`, `N`, `Standard Error`, `Lower CI Bound`, `Upper CI Bound`, `Recommend Suppress`, `Not Relevant`, `Date`, `Domain Source`.
- `Abilities.txt`: `O*NET-SOC Code`, `Element ID`, `Element Name`, `Scale ID`, `Data Value`, `N`, `Standard Error`, `Lower CI Bound`, `Upper CI Bound`, `Recommend Suppress`, `Not Relevant`, `Date`, `Domain Source`.
- `Work Activities.txt`: `O*NET-SOC Code`, `Element ID`, `Element Name`, `Scale ID`, `Data Value`, `N`, `Standard Error`, `Lower CI Bound`, `Upper CI Bound`, `Recommend Suppress`, `Not Relevant`, `Date`, `Domain Source`.
- `Task Statements.txt`: `O*NET-SOC Code`, `Task ID`, `Task`, `Task Type`, `Incumbents Responding`, `Date`, `Domain Source`.
- `Task Ratings.txt`: `O*NET-SOC Code`, `Task ID`, `Scale ID`, `Category`, `Data Value`, `N`, `Standard Error`, `Lower CI Bound`, `Upper CI Bound`, `Recommend Suppress`, `Date`, `Domain Source`.
- `Task Categories.txt`: `Scale ID`, `Category`, `Category Description`.
- `Technology Skills.txt`: `O*NET-SOC Code`, `Example`, `Commodity Code`, `Commodity Title`, `Hot Technology`, `In Demand`.
- `Tools Used.txt`: `O*NET-SOC Code`, `Example`, `Commodity Code`, `Commodity Title`.
- `Education, Training, and Experience.txt`: `O*NET-SOC Code`, `Element ID`, `Element Name`, `Scale ID`, `Category`, `Data Value`, `N`, `Standard Error`, `Lower CI Bound`, `Upper CI Bound`, `Recommend Suppress`, `Date`, `Domain Source`.
- `Education, Training, and Experience Categories.txt`: `Element ID`, `Element Name`, `Scale ID`, `Category`, `Category Description`.
- `Alternate Titles.txt`: `O*NET-SOC Code`, `Alternate Title`, `Short Title`, `Source(s)`.
- `Job Zones.txt`: `O*NET-SOC Code`, `Job Zone`, `Date`, `Domain Source`.
- `Job Zone Reference.txt`: `Job Zone`, `Name`, `Experience`, `Education`, `Job Training`, `Examples`, `SVP Range`.
