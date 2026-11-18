# Project Guide

An orientation map of the repository, built from folder layout, file names,
config files, imports and module docstrings. Most files were **not** read in
full. A `?` marks a description that is an educated guess, not a verified fact.

For the authoritative project documents see `docs/MASTER_PLAN.md` (intended
design), `docs/PROJECT_STATE.md` (what is actually implemented) and
`docs/DECISIONS.md` (decision log).

## 1. Overview

**What it does.** A Bachelor-thesis research app for explainable skill-gap job
matching. Candidates upload CVs and jobs are imported; the system extracts
skills, qualifications and occupations, links them to the ESCO and O\*NET
taxonomies, retrieves relevant jobs with dense embeddings (Phase 5), and then
produces an explainable, rule-based match with skill gaps
(Matched / Partially Covered / Missing) in Phase 6. It is a career
decision-support tool, not a hiring system.

**Tech stack.**

| Part | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn |
| Database | PostgreSQL 16 with the pgvector extension |
| NLP | Dictionary + regex extraction (optional spaCy); local `multilingual-e5-small` embedding model for retrieval |
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Query, React Router |
| Deployment | Docker Compose (db, backend, migrate, frontend, nginx) |
| Tests | pytest (backend); Node test runner + Playwright browser tests (frontend) |

**How it starts.**

- `docker-compose.yml` starts five services: `db` (pgvector Postgres, port 5432),
  `backend` (port 8000), `frontend` (port 5173), `nginx` (port 8080) and an
  on-demand `migrate` service (`alembic upgrade head`, profile `maintenance`).
- Backend container command (`backend/Dockerfile`):
  `python -m app.utils.check_migrations` (refuses to start if the database
  schema is not at the latest migration), then
  `uvicorn app.main:app`.
- Backend entry point: `backend/app/main.py` → `create_app()` registers the
  API routers (`/health`, `/auth`, `/candidates`, `/cvs`, `/jobs`, `/matches`,
  `/matching-inputs`, `/matching-runs`, `/retrieval`, `/taxonomy`, `/admin`).
- Frontend entry point: `frontend/index.html` → `frontend/src/main.tsx` →
  `frontend/src/App.tsx` (routes and login guard).

**How it connects to the database.**

- `DATABASE_URL` (from `.env` / compose; default
  `postgresql+psycopg://skillgap:skillgap@db:5432/skillgap`) is read by
  `backend/app/core/config.py`.
- `backend/app/db/session.py` creates the SQLAlchemy engine and a
  `get_db()` session dependency that routes inject.
- Tables are defined in `backend/app/db/models/` and created/changed only
  through Alembic migrations in `backend/app/db/migrations/versions/`.

**Request flow (architecture).** Frontend page → `frontend/src/api/*` →
FastAPI route (`backend/app/api/routes/`) → service (`backend/app/services/`) →
repository (`backend/app/repositories/`) → database, with pure domain logic in
`nlp/`, `taxonomy/`, `retrieval/` and `matching/`.

## 2. File inventory

Skipped: `.git`, `node_modules`, `dist`, `__pycache__`, `.venv`, `.pytest_cache`,
`.DS_Store`, and the private, git-ignored folders described under "Other".

### UI / pages (frontend)

| Path | Purpose |
|---|---|
| `frontend/index.html` | HTML shell that loads `src/main.tsx`. |
| `frontend/src/main.tsx` | Frontend entry: mounts React, router and React Query. |
| `frontend/src/App.tsx` | Route table and the login-required wrapper. |
| `frontend/src/layouts/AppLayout.tsx` | Page frame and navigation for signed-in users. |
| `frontend/src/styles.css` | Global styles (Tailwind plus matching-screen styles). |
| `frontend/src/vite-env.d.ts` | Vite TypeScript type declarations. |
| `frontend/src/pages/LoginPage.tsx` | Sign-in page. |
| `frontend/src/pages/RegisterPage.tsx` | Account registration page. |
| `frontend/src/pages/DashboardPage.tsx` | Landing page after sign-in (?: overview/links). |
| `frontend/src/pages/CvsPage.tsx` | Upload/paste CVs, view parsed sections and extracted skills. |
| `frontend/src/pages/JobsPage.tsx` | Create/import jobs, view job skills; also holds the legacy prototype recommendations button. |
| `frontend/src/pages/TaxonomyPage.tsx` | Taxonomy import/search and mapping review (admin/researcher). |
| `frontend/src/pages/MatchingPage.tsx` | Phase 6: create and view explainable matching runs. |
| `frontend/src/pages/MatchingFactsPage.tsx` | Phase 6: candidate's own occupation/qualification/experience facts. |
| `frontend/src/pages/JobInventoryPage.tsx` | Phase 6: manager/researcher review of a job's requirements, groups and sign-off. |
| `frontend/src/pages/AboutPage.tsx` | Static "about" page. |
| `frontend/src/pages/PrivacyPage.tsx` | Static privacy notice. |
| `frontend/src/components/AuthCard.tsx` | Shared card layout for login/register forms. |
| `frontend/src/components/FormField.tsx` | Reusable labelled form input. |
| `frontend/src/components/SectionList.tsx` | Shows detected CV/job sections. |
| `frontend/src/components/TextPreview.tsx` | Shows extracted/cleaned document text. |
| `frontend/src/components/SkillReviewPanel.tsx` | Approve/reject extracted skills. |
| `frontend/src/components/TaxonomyReviewPanel.tsx` | Review taxonomy links for extracted terms. |
| `frontend/src/components/CandidateSkillGroups.tsx` | Candidate's normalized skills, grouped (polls the API every 30 s). |
| `frontend/src/components/JobMatchPanel.tsx` | Legacy prototype match display (`/matches`). |
| `frontend/src/components/matching/Controls.tsx` | Shared small pieces for matching screens (error notice, loading, enum lists). |
| `frontend/src/components/matching/FactForm.tsx` | Form for adding a matching fact. |
| `frontend/src/components/matching/RunDetails.tsx` | Renders a matching run's results, components, gaps and evidence. |
| `frontend/src/components/matching/CandidateFactsPanel.tsx` | **Uncommitted, new.** ? Candidate facts panel, imported by the CV/facts pages. |
| `frontend/src/components/matching/JobSkillReview.tsx` | **Uncommitted, new.** ? Job skill review panel for the inventory page. |
| `frontend/src/components/matching/ReviewSummary.tsx` | **Uncommitted, new.** ? Review status summary. |
| `frontend/src/api/client.ts` | Fetch wrapper: base URL, auth header, `ApiError`. |
| `frontend/src/api/auth.ts` | Auth API calls (register, login, refresh, logout, me). |
| `frontend/src/api/documents.ts` | CV, job, skill and legacy match API calls. |
| `frontend/src/api/taxonomy.ts` | Taxonomy API calls. |
| `frontend/src/api/matching.ts` | Phase 6 matching-inputs and matching-runs API calls. |
| `frontend/src/types/auth.ts` | TypeScript types for users/roles/tokens. |
| `frontend/src/types/documents.ts` | Types for CVs, jobs, skills, legacy matches. |
| `frontend/src/types/taxonomy.ts` | Types for taxonomy data. |
| `frontend/src/types/matching.ts` | Types for Phase 6 facts, groups, runs and evidence. |
| `frontend/src/features/auth/AuthProvider.tsx` | React context holding the signed-in user and tokens. |
| `frontend/src/features/auth/tokenStorage.ts` | Saves/loads tokens in browser storage. |
| `frontend/src/hooks/.gitkeep` | Empty placeholder folder. |
| `frontend/src/utils/.gitkeep` | Empty placeholder folder. |

### API routes (backend, thin HTTP layer)

| Path | Purpose |
|---|---|
| `backend/app/main.py` | Backend entry point; builds the FastAPI app and registers routers. |
| `backend/app/api/dependencies/auth.py` | `get_current_user` and role checks used by routes. |
| `backend/app/api/routes/health.py` | `/health` liveness check. |
| `backend/app/api/routes/auth.py` | Register, login, refresh, logout. |
| `backend/app/api/routes/candidates.py` | Read/update the signed-in candidate's profile. |
| `backend/app/api/routes/cvs.py` | Upload/paste/list/delete CVs and their skills. |
| `backend/app/api/routes/jobs.py` | Create/import/list jobs and review their extracted skills. |
| `backend/app/api/routes/matches.py` | **Legacy** prototype recommendations (`/matches`). |
| `backend/app/api/routes/matching_inputs.py` | Phase 6 reviewed inputs: facts, groups, occurrence reviews, inventory sign-off, manual capabilities. |
| `backend/app/api/routes/matching_runs.py` | Phase 6 runs: create, read current, read by id (owner only). |
| `backend/app/api/routes/retrieval.py` | Phase 5 dense retrieval of top-N jobs. |
| `backend/app/api/routes/taxonomy.py` | Taxonomy import, search, linking and review. |
| `backend/app/api/routes/admin.py` | Admin views: processing logs, mapping review queue. |

### Services / business logic

| Path | Purpose |
|---|---|
| `backend/app/services/auth_service.py` | Registration, login, token issue/refresh. |
| `backend/app/services/candidate_service.py` | Candidate profile logic. |
| `backend/app/services/cv_service.py` | CV upload/paste pipeline: parse, clean, sections, extract. |
| `backend/app/services/job_service.py` | Job creation/import pipeline and job skill review. |
| `backend/app/services/document_parser_service.py` | Reads PDF/DOCX/TXT into text, validates type/size. |
| `backend/app/services/pdf_text_normalization_service.py` | Repairs PDF text artifacts (line breaks, hyphenation ?). |
| `backend/app/services/text_cleaning_service.py` | General text cleanup. |
| `backend/app/services/section_detection_service.py` | Splits documents into sections (experience, education…). |
| `backend/app/services/skill_service.py` | Runs extraction and manages skill review status. |
| `backend/app/services/processing_log_service.py` | Writes processing log entries. |
| `backend/app/services/taxonomy_service.py` | Taxonomy import (incl. sample data from `/data/sample`), linking, review. |
| `backend/app/services/retrieval_service.py` | Builds embeddings/index and retrieves jobs. |
| `backend/app/services/matching_service.py` | **Legacy** exact-skill prototype matcher behind `/matches`. |
| `backend/app/services/matching_inputs_service.py` | Phase 6 reviewed-input rules and inventory sign-off validation. |
| `backend/app/services/matching_runs_service.py` | Phase 6 run orchestration, snapshots, currentness checks. |
| `backend/app/nlp/skill_extractor.py` | Dictionary/regex (optional spaCy) term extractor. |
| `backend/app/nlp/skill_dictionary.json` | Skill dictionary used by the extractor. |
| `backend/app/taxonomy/packages.py` | Version-pinned ESCO/O\*NET ZIP readers (no network). |
| `backend/app/taxonomy/importer.py` | Parses taxonomy packages into records. |
| `backend/app/taxonomy/onet_31.py` | O\*NET 31.0 CSV parser. |
| `backend/app/taxonomy/onet_31_manifest.json` | Expected file/hash manifest for O\*NET 31.0. |
| `backend/app/taxonomy/linker.py` | Exact/alternative/normalized/fuzzy term-to-concept linking. |
| `backend/app/taxonomy/normalization.py` | Text normalization for taxonomy matching. |
| `backend/app/retrieval/embedder.py` | Loads the local e5 model and produces embeddings. |
| `backend/app/retrieval/representation.py` | Builds the text representation of profiles/jobs that gets embedded. |
| `backend/app/retrieval/job_budget.py` | Template-v2 rules for which job text fits the token budget. |
| `backend/app/retrieval/cli.py` | Command line for provisioning the model and indexing. |
| `backend/app/retrieval/benchmark.py` | Offline Phase 5 relevance-benchmark tooling. |
| `backend/app/retrieval/evaluation.py` | Retrieval metrics. |
| `backend/app/retrieval/evaluation_policy.py` | Which queries count in the Phase 5 evaluation. |
| `backend/app/matching/policy.py` | Pure matching-policy-v1 scoring rules (weights, exact fractions). |
| `backend/app/matching/assessment.py` | Turns stored reviewed inputs into policy components for one candidate–job pair. |
| `backend/app/matching/manual_capabilities.py` | Duplicate/conflict checks for manually entered job capabilities. |
| `backend/app/matching/public_evidence.py` | Allowlist that strips private fields from candidate-visible results. |
| `backend/app/core/security.py` | Password hashing and JWT creation/verification. |
| `backend/app/workers/__init__.py` | Empty placeholder ("background worker entry points"). |
| `backend/app/evaluation/__init__.py` | Empty placeholder ("evaluation interfaces for later phases"). |

### Data access (repositories and database setup)

| Path | Purpose |
|---|---|
| `backend/app/db/session.py` | Engine and `get_db()` session dependency. |
| `backend/app/db/base.py` | SQLAlchemy `Base` and timestamp mixin. |
| `backend/app/db/migrations/env.py` | Alembic runtime configuration. |
| `backend/app/db/migrations/script.py.mako` | Template for new migration files. |
| `backend/app/db/migrations/versions/0001_foundation_auth.py` | Users, roles, refresh tokens. |
| `backend/app/db/migrations/versions/0002_document_processing.py` | CVs, jobs, sections, processing logs. |
| `backend/app/db/migrations/versions/0003_skill_extraction.py` | Extracted terms and skills. |
| `backend/app/db/migrations/versions/0004_candidate_job_matching.py` | Legacy prototype match tables. |
| `backend/app/db/migrations/versions/0005_taxonomy_integration.py` | Taxonomy tables and links. |
| `backend/app/db/migrations/versions/0006_official_taxonomy.py` | Official ESCO/O\*NET release support. |
| `backend/app/db/migrations/versions/0007_taxonomy_review_audit.py` | Taxonomy review audit trail. |
| `backend/app/db/migrations/versions/0008_dense_retrieval.py` | pgvector embedding tables. |
| `backend/app/db/migrations/versions/0009_explainable_matching.py` | Phase 6 facts, groups, runs, results, gaps. |
| `backend/app/db/migrations/versions/0010_matching_input_integrity.py` | Phase 6 integrity triggers and constraints. |
| `backend/app/db/migrations/versions/0011_manual_job_capabilities.py` | Manual job capabilities table. |
| `backend/app/repositories/auth_repository.py` | User/role/token queries. |
| `backend/app/repositories/document_repository.py` | CV, job, section, skill and legacy-match queries. |
| `backend/app/repositories/taxonomy_repository.py` | Taxonomy queries. |
| `backend/app/repositories/retrieval_repository.py` | Embedding storage and vector search. |
| `backend/app/repositories/matching_inputs_repository.py` | Phase 6 reviewed-input storage and fingerprints. |
| `backend/app/repositories/matching_runs_repository.py` | Phase 6 run storage. |

### Models and schemas

| Path | Purpose |
|---|---|
| `backend/app/db/models/auth.py` | ORM: User, Role, RefreshToken. |
| `backend/app/db/models/documents.py` | ORM: candidate profile, CVs, sections, jobs, extracted terms/skills, legacy matches. |
| `backend/app/db/models/taxonomy.py` | ORM: taxonomy sources, versions, concepts, labels, links. |
| `backend/app/db/models/retrieval.py` | ORM: candidate and job embeddings. |
| `backend/app/db/models/explainable.py` | ORM: Phase 6 scoring config, facts, groups, runs, results. |
| `backend/app/schemas/auth.py` | API request/response shapes for auth. |
| `backend/app/schemas/documents.py` | API shapes for CVs, jobs, skills. |
| `backend/app/schemas/taxonomy.py` | API shapes for taxonomy. |
| `backend/app/schemas/retrieval.py` | API shape for retrieved jobs. |
| `backend/app/schemas/matching_inputs.py` | API shapes for Phase 6 reviewed inputs. |
| `backend/app/schemas/matching_runs.py` | API shape for creating a run. |

### Config

| Path | Purpose |
|---|---|
| `.env.example` | Template for `.env` (DB URL, secret key, CORS, API URL). |
| `.gitignore` | Ignore rules (incl. private evaluation data, models, dumps). |
| `docker-compose.yml` | Runs db, backend, migrate, frontend, nginx. |
| `nginx/default.conf` | Reverse proxy on port 8080: `/api/…` goes to the backend, everything else to the frontend. |
| `backend/Dockerfile` | Backend image; checks migrations then starts Uvicorn. |
| `backend/alembic.ini` | Alembic settings. |
| `backend/pytest.ini` | pytest settings. |
| `backend/requirements/base.txt` | Runtime Python dependencies. |
| `backend/requirements/dev.txt` | Test/dev Python dependencies. |
| `backend/app/core/config.py` | Settings loaded from environment / `.env`. |
| `frontend/package.json` / `package-lock.json` | Frontend dependencies and npm scripts (`dev`, `build`, `test`, `test:browser`). |
| `frontend/vite.config.ts` | Vite build/dev server config. |
| `frontend/tsconfig.json` | TypeScript config. |
| `frontend/tailwind.config.js`, `frontend/postcss.config.js` | Tailwind/PostCSS config. |
| `frontend/Dockerfile` | Builds the frontend and serves it with nginx. |
| `frontend/nginx.conf` | nginx config inside the frontend container (SPA routing ?). |

### Tests

| Path | Purpose |
|---|---|
| `backend/tests/conftest.py` | Shared fixtures (test DB, users, stubbed model). |
| `backend/tests/test_auth.py`, `test_health.py`, `test_job_permissions.py` | Auth, health and role permissions. |
| `backend/tests/test_document_processing.py`, `test_cv_lifecycle_postgres.py` | Parsing, cleaning, CV lifecycle. |
| `backend/tests/test_skill_extraction.py`, `test_job_skill_correction_postgres.py` | Extraction and job skill corrections. |
| `backend/tests/test_candidate_profile_reads.py`, `test_candidate_skill_groups.py` | Candidate profile and grouped skills. |
| `backend/tests/test_taxonomy*.py`, `test_official_packages.py`, `test_onet31.py` | Taxonomy import, linking, review, packages. |
| `backend/tests/test_retrieval*.py`, `test_representation_v2.py`, `test_evaluation_policy.py` | Phase 5 retrieval, templates, benchmark, evaluation rules (`test_retrieval_real_model.py` needs the real model). |
| `backend/tests/test_matching_*.py`, `test_manual_capabilit*.py` | Phase 6 policy, assessment, inputs, runs, integrity, privacy. `*_postgres.py` variants need a real PostgreSQL. |
| `backend/tests/test_migration_check.py` | The startup migration-head check. |
| `backend/tests/fixtures/taxonomy/**`, `fixtures/onet31/**` | Small ESCO/O\*NET sample files used by taxonomy tests. |
| `frontend/tests/run.mjs` | Runs `matching.test.tsx` (bundles with esbuild, Node test runner). |
| `frontend/tests/matching.test.tsx` | Component/API tests for matching screens. |
| `frontend/tests/matching.browser.mjs` | Playwright browser tests with mocked API. |
| `frontend/tests/fixtures.mjs` | Shared synthetic data for browser tests. |
| `frontend/tests/README.md` | How to run the frontend tests. |

### Scripts (one-off and maintenance)

| Path | Purpose |
|---|---|
| `backend/app/utils/check_migrations.py` | Startup guard: DB schema must match the code's latest migration. |
| `backend/app/utils/manage_role.py` | CLI to grant a role to a user (documented in README). |
| `backend/app/scripts/verify_taxonomy_package.py` | Verifies a taxonomy ZIP package (Phase 4 evidence). |
| `backend/app/scripts/verify_onet31.py` | O\*NET 31.0 round-trip verification in a throwaway schema (Phase 4 evidence). |
| `backend/scripts/verify_phase5_real.py` | One-shot Phase 5 real-model evidence run. |

### Docs

| Path | Purpose |
|---|---|
| `README.md` | Project intro, setup, phase summary. |
| `AGENTS.md` | Rules for AI coding agents working in this repo. |
| `docs/MASTER_PLAN.md` | Intended final system and phases. |
| `docs/PROJECT_STATE.md` | What is implemented now (long running log). |
| `docs/DECISIONS.md` | Architectural/methodological decisions (D001…D035). |
| `docs/architecture.md`, `database-erd.md`, `processing-flow.md`, `privacy.md` | Architecture, schema diagram, processing pipeline, privacy notes. |
| `docs/taxonomy-integration.md`, `onet-31-contract.md`, `phase4-verification.md` | Phase 4 taxonomy design and verification. |
| `docs/phase5-dense-retrieval.md`, `phase5-evaluation-protocol.md` | Phase 5 retrieval design and evaluation rules. |
| `docs/phase6-explainable-matching.md`, `phase6-evaluation-protocol.md`, `phase6-fact-entry-protocol.md`, `phase6-manual-job-capabilities.md` | Phase 6 matching design, evaluation and data-entry rules. |
| `docs/verification/*` | Recorded verification evidence (taxonomy package checks, Phase 5 model/template results). |

### Other (data and local-only material)

| Path | Purpose |
|---|---|
| `data/sample/esco_sample.json`, `onet_sample.json`, `esco_onet_mappings_sample.json` | Development sample taxonomy loaded by `taxonomy_service` (not official releases). |
| `data/sample/skill_dictionary.json` | Copy of the extractor dictionary (see cleanup list). |
| `data/evaluation/.gitkeep`, `data/taxonomy/.gitkeep` | Empty placeholder folders (mounted into the backend as `/data`). |
| `evaluation/templates/*` | Empty templates for Phase 5 evaluation inputs (candidates, jobs, judgments, policy, DB mapping). |
| `evaluation/local/` | **Git-ignored, private.** Evaluation corpus, review records, deployment and migration evidence. Not described file-by-file here on purpose. |
| `models/` | **Git-ignored.** Local copy of the `multilingual-e5-small` embedding model. |
| `ESCO dataset - v1.2.1 - …/`, `esco-1.2.1-en.zip`, `db_31_0_csv.zip` | **Git-ignored.** Downloaded official ESCO / O\*NET packages. |
| `phase4-*.dump` (3 files) | **Git-ignored.** Database backups taken before Phase 4 upgrades. |
