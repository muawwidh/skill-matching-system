# Skill Gap Job Matching System — Agent Instructions

## Project Purpose

This repository contains a Bachelor thesis project for an explainable
skill-gap job matching system using ESCO/O*NET taxonomies and dense retrieval.

The application is a career decision-support system, not an automated
candidate-selection or hiring system.

## Required Context

Before making substantial changes, read:

1. docs/MASTER_PLAN.md
2. docs/PROJECT_STATE.md
3. docs/DECISIONS.md
4. docs/architecture.md
5. Relevant implementation files and tests

The repository is the source of truth for actual implementation.

MASTER_PLAN.md describes the intended final system.

PROJECT_STATE.md describes what is currently implemented and which phase
is active.

Do not assume a planned feature is already implemented.

## Development Workflow

Development is phase-based.

Do not skip phases unless explicitly instructed.

Before starting a new phase:

- inspect the existing implementation
- verify the previous phase
- run relevant backend tests
- run the frontend production build
- verify database migrations
- verify Docker where applicable
- check PROJECT_STATE.md

Do not declare a phase complete simply because code was written.

A phase is complete only after its required behavior is verified.

## Architecture

Preserve:

Frontend
→ API Routes
→ Services
→ Repositories
→ Database / NLP / Taxonomy / Matching / Evaluation

FastAPI routes must remain thin.

Business logic belongs in services/domain modules.

Database operations belong in repositories.

Do not unnecessarily redesign working architecture.

## Database

Use PostgreSQL.

Use SQLAlchemy.

All schema changes require Alembic migrations.

Do not edit already-applied migrations to represent new schema changes.
Create a new migration.

## Backend

Primary stack:

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL

Use type hints and keep modules independently testable.

## Frontend

Primary stack:

- React
- TypeScript
- Vite
- React Query
- Tailwind

Keep Candidate and Administrator/Researcher functionality clearly separated.

The frontend visual design may be redesigned later without changing
backend behavior or API contracts unnecessarily.

## Document Processing

Supported baseline formats:

- readable PDF
- DOCX
- TXT

Scanned PDFs are not assumed to work unless OCR is deliberately added later.

## Skill Extraction

Preserve extraction evidence.

Repeated extracted occurrences of one skill may remain because each can
represent separate evidence.

Candidate-facing normalized skills should not display unnecessary duplicates.

Manual review decisions must remain stored.

Rejected skills must not be treated as confirmed candidate skills.

## Taxonomy

ESCO and O*NET are versioned local taxonomy sources.

Do not depend on live ESCO/O*NET API requests during each match.

Bundled sample datasets are development/testing data only.

Do not represent sample releases as official taxonomy releases.

Taxonomy linking may use:

1. exact preferred label
2. exact alternative label
3. normalized match
4. fuzzy match
5. semantic/embedding match later

High-confidence deterministic matches may be automatically approved.

Uncertain mappings must remain reviewable.

Do not silently lower thresholds just to increase automatic matching.

## Dense Retrieval

Dense retrieval belongs to Phase 5.

Embeddings retrieve top-N relevant jobs.

Vector similarity is NOT the final match score.

Embedding model/version information must be recorded for reproducibility.

## Matching

A basic matching prototype already exists from earlier development.

It belongs conceptually to Phase 6 and must NOT be mistaken for the
completed final matching system.

Final Phase 6 scoring must be transparent, configurable and versioned.

Planned components include:

- semantic similarity
- required skill coverage
- preferred skill coverage
- occupation alignment
- qualification/experience alignment
- critical-skill penalty

## Skill Gaps

Final classifications must support:

- Matched
- Partially Covered
- Missing

Explanations must derive from stored structured evidence.

Never generate unsupported explanations.

## Privacy

Do not use irrelevant personal characteristics for matching, including:

- age
- gender
- religion
- nationality
- marital status
- photographs
- unrelated personal attributes

System-wide administrative information must not be visible to ordinary
candidate accounts.

## Testing

Every meaningful feature should include tests.

Do not remove or weaken valid tests merely to make a build pass.

When fixing bugs, add regression tests where practical.

Before reporting work complete, report:

- tests run
- results
- frontend build status where relevant
- migrations added/applied
- significant files changed
- unresolved issues

## Documentation

Update docs/PROJECT_STATE.md whenever meaningful implementation state changes.

Update docs/DECISIONS.md only when a genuine architectural or methodological
decision changes or is introduced.

DECISIONS.md is not a changelog.

## Git

Do not rewrite Git history without explicit permission.

Never commit:

- .env
- credentials
- virtual environments
- node_modules
- build artifacts
- private uploaded CV files
- generated database data

Use Git checkpoints for verified phases.

## Agent Behaviour

Before modifying code:

1. inspect the repository
2. read the project context files
3. determine the active phase
4. compare the requested work with MASTER_PLAN.md
5. identify affected modules
6. preserve working behavior unless a change is required

If documentation conflicts with actual code, investigate the repository.

Do not guess.

Do not claim functionality works without verifying it.