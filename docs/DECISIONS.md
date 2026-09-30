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