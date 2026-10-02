# O*NET 31.0 CSV contract

This adapter implements **ONET-31.0-csv**, not 31.0 TXT or generic O*NET support.
The independently pinned **ONET-29.0-txt** parser and regression evidence remain.

## Exact package

The supplied `db_31_0_csv.zip` identifies O*NET 31.0, August 2026, in Read Me.txt.
SHA-256: `55033fc68b4c13ec23e7f74dc6378660f6e854e75d55d6e333ae0a761d3987cd`.
The checked-in `backend/app/taxonomy/onet_31_manifest.json` is the authoritative
filename, required-header and dataset-specific identity manifest for all 45 CSVs.
All 45 are required, as is Read Me.txt with the exact first-line release declaration.
No optional data files or invented Tools Used dataset are part of this contract.

UTF-8 with optional BOM; comma delimiter, quoted fields and multiline strings.
Header order may vary. Missing/duplicate headers, malformed rows, invalid encoding,
missing required files, duplicate record identities and unresolved references fail
before replacement. Extra columns are preserved in source_data. Unknown files are
reported as skipped with hashes/reasons; Read Me.txt is validated metadata rather
than an inserted dataset. This does not authenticate publisher provenance.

Shared bounded ZIP checks enforce 128 MiB upload/member, 512 MiB total and 128
entries, including runtime decompressed-byte checks. Unsafe paths, encrypted or
symlink members, duplicate basenames and corrupt archives fail. Wrapper directories
are permitted. Dispatch is by declared source/version followed by exact validation;
CSV is never reinterpreted as renamed 29.0 TXT.

## Source preservation and identities

Every CSV row becomes a release-scoped onet_data_records row with the full string
field dictionary in source_data. Known occupation/element/scale/task/category fields
and exact Decimal Data Value are additionally projected into typed columns. Other
statistics, dates, flags, descriptive fields, additional numerical fields and
provenance retain their supplied values in source_data, not approximate labels.

Record keys hash the ordered identity columns declared separately for each dataset.
For example, software keys include occupation, element and Workplace Example;
binary element relationships include both directional IDs. Task links include
occupation/task/DWA, triples include all three endpoints, anchors include Anchor
Value, and metadata includes occupation/Item/Response/Date. Duplicate identities
fail even if only a descriptive/statistical field differs; no source row is merged.

Essential Skills (2.A) and Transferable Skills (2.B) stay separate datasets.
Education and Training/Experience and their categories remain separate. Category
validation includes element and scale; RL and RQ are not interchangeable. Scale
bounds come from this release, including WI -3 to 3. Job-zone references represent
combined Zone 1-2 using code 2, then codes 3, 4, 5.

## Concepts and relationships

All content_model_reference rows become concepts using their exact Element ID.
Descendants of 2.A/2.B are skill, 2.C knowledge, 1.A ability, 4.A work_activity,
2.E software_skill; other nodes are content_element. Root/category nodes are not
asserted to be individual skills. Occupations materialize as ONET:<O*NET-SOC Code>.
Job titles supply occupation aliases. Workplace examples remain source rows, not
invented interchangeable concepts. No cross-release equivalence is inferred.

Binary element relationship files materialize first-named endpoint to second-named
endpoint, with the dataset stem as relationship_type and the complete row metadata.
related_occupations materializes occupation to Related O*NET-SOC Code. All endpoints
are release scoped. Three-endpoint GWA/IWA/DWA and task/DWA rows remain complete
validated records; they are not flattened into misleading binary associations.
The report separately counts resolved relationship source rows and graph edges.
All occupation/element/scale references, task and original-task references, and
education/training/work-context/task categories are checked within this package.

The existing schema supports these semantics; no new migration is needed. Import
retains source advisory locking, single-transaction replacement/activation and
rollback. Successful same-version replacement recreates dependent records; reviewed
links/mappings may cascade away exactly as documented previously.

## Verification and attribution

Representative fixtures are attributed subsets, not full-release evidence.
Full verification uses `python -m app.scripts.verify_onet31 PACKAGE --output REPORT`
with DATABASE_URL pointing to PostgreSQL **phase4_verify**, no search_path override.
It creates and removes its own unique schema, migrates to head, imports and replaces
the package, and compares every source field by key in fresh sessions for both runs.
It records per-file counts/hashes, graph direction checks, revision and durations.
The full verifier requires the exact inspected archive checksum.

O*NET 31.0 Database, National Center for O*NET Development, licensed CC BY 4.0.
Source: https://www.onetcenter.org/database.html
Package dictionary: https://www.onetcenter.org/dictionary/31.0/csv/
License: https://www.onetcenter.org/license_db.html
Changes: conversion to local structured records, concept/relationship projections,
and subset selection for fixtures. Source field values are retained unchanged;
no endorsement by the original publisher is implied.

## Full-package evidence

`docs/verification/onet-31.0.json` records successful isolated PostgreSQL initial
import and same-version replacement. Both runs compared every source field by
dataset-specific key in fresh sessions: 1,120,006 rows, 4,022 concepts (including
1,016 occupations), and 20,262 binary relationships with verified directions.
No unresolved references. Initial run: 74.576 seconds; replacement: 101.420 seconds;
total including migration setup: 176.141 seconds. The disposable schema was removed.
The only skipped member was Read Me.txt (validated release metadata, not a dataset).
No CSV dataset was skipped. Counts below were verified on both runs.

| Exact CSV filename | Source rows | Database rows |
| --- | ---: | ---: |
| `abilities_to_work_activities.csv` | 381 | 381 |
| `abilities_to_work_context.csv` | 139 | 139 |
| `abilities.csv` | 94640 | 94640 |
| `career_interest_type_keywords.csv` | 75 | 75 |
| `career_interest_types.csv` | 8307 | 8307 |
| `content_model_reference.csv` | 3006 | 3006 |
| `education_categories.csv` | 24 | 24 |
| `education.csv` | 11495 | 11495 |
| `emerging_tasks.csv` | 338 | 338 |
| `essential_skills_to_work_activities.csv` | 110 | 110 |
| `essential_skills_to_work_context.csv` | 39 | 39 |
| `essential_skills.csv` | 18200 | 18200 |
| `gwas_to_iwas_to_dwas.csv` | 2087 | 2087 |
| `gwas_to_iwas.csv` | 332 | 332 |
| `interests_illustrative_activities.csv` | 188 | 188 |
| `interests_illustrative_occupations.csv` | 186 | 186 |
| `job_titles.csv` | 54269 | 54269 |
| `job_zone_reference.csv` | 4 | 4 |
| `job_zones.csv` | 923 | 923 |
| `knowledge.csv` | 60060 | 60060 |
| `level_scale_anchors.csv` | 483 | 483 |
| `occupation_data.csv` | 1016 | 1016 |
| `occupation_level_metadata.csv` | 32280 | 32280 |
| `related_occupations.csv` | 18460 | 18460 |
| `sample_of_reported_titles.csv` | 8189 | 8189 |
| `scales_reference.csv` | 33 | 33 |
| `software_skills.csv` | 31821 | 31821 |
| `specific_interest_areas_to_career_interest_types.csv` | 53 | 53 |
| `specific_interest_areas.csv` | 73062 | 73062 |
| `survey_booklet_locations.csv` | 211 | 211 |
| `task_categories.csv` | 7 | 7 |
| `task_ratings.csv` | 165780 | 165780 |
| `task_statements.csv` | 18838 | 18838 |
| `tasks_to_dwas.csv` | 24087 | 24087 |
| `training_and_experience_categories.csv` | 29 | 29 |
| `training_and_experience.csv` | 26812 | 26812 |
| `transferable_skills_to_work_activities.csv` | 122 | 122 |
| `transferable_skills_to_work_context.csv` | 57 | 57 |
| `transferable_skills.csv` | 45500 | 45500 |
| `work_activities.csv` | 74702 | 74702 |
| `work_context_categories.csv` | 281 | 281 |
| `work_context.csv` | 305389 | 305389 |
| `work_styles_to_work_activities.csv` | 303 | 303 |
| `work_styles_to_work_context.csv` | 266 | 266 |
| `work_styles.csv` | 37422 | 37422 |
