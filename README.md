# SkillGap – Skill Gap Job Matching

SkillGap is a career guidance tool. A candidate adds a CV, confirms the skills
found in it, and sees the jobs that fit their skills best, with the skills they
already have and the skills they would still need for each job.

Skills and occupations follow the European ESCO classification (with O*NET as
a second, optional taxonomy). Jobs are ranked by dense retrieval with a local
embedding model; each job is then explained by its skill coverage. There is no
match percentage, and nothing in the system selects or rejects candidates.

> Career guidance only — not a hiring decision. A candidate's results are
> visible only to that candidate.

![Dashboard](docs/images/dashboard.png)
<!-- Screenshot placeholder: dashboard -->

## Features

**For candidates**

- Add CVs by upload (readable PDF, DOCX, TXT) or by pasting text, after giving consent.
- Review the skills found in each CV: confirm, reject, correct, or add skills by hand.
  Only confirmed skills are used.
- Check which ESCO concept a skill is linked to, and correct the link.
- Jobs page: the best-matching jobs (top 100 by similarity, shown in pages of
  10, 25 or 50). For each job: required and preferred skills you have, related
  skills in your profile, skills to develop, and requirements the system does
  not assess (qualifications, certificates).
- Optional work experience (job title, months, ESCO occupation) to see years of
  related experience next to each job, and an optional filter that hides jobs
  above your experience.
- Dashboard with profile setup steps, top matches and the skills that are
  missing most often in your top 10 jobs.
- Delete a CV, or the whole account and all its data.

**For administrators and researchers**

- Import versioned ESCO and O*NET releases; search concepts; review uncertain
  skill-to-concept links.
- Add jobs by hand and review the skills extracted from them.
- Import live jobs from public job APIs (administrators).
- System overview with totals only, never one person's results (administrators).

![Jobs page](docs/images/jobs.png)
<!-- Screenshot placeholder: Jobs page with the detail panel -->

![My profile](docs/images/profile.png)
<!-- Screenshot placeholder: My profile -->

## Technology

- Backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic
- Database: PostgreSQL 16 with pgvector
- Embeddings: `intfloat/multilingual-e5-small` (pinned revision), sentence-transformers, CPU only
- Frontend: React, TypeScript, Vite, Tailwind CSS, React Query
- Deployment: Docker Compose, Nginx

See [docs/architecture.md](docs/architecture.md) for components and data flow.

## Setup with Docker

Requirements: Docker with Compose and a few GB of free disk space (the backend
image with PyTorch for CPU is about 1.8 GB, the model about 0.5 GB).

```bash
cp .env.example .env          # then set SECRET_KEY to a long random value
docker compose up -d db
docker compose build backend
docker compose --profile maintenance run --rm migrate    # create the database schema
```

### 1. Provision the embedding model

The model is downloaded once into `models/` (not part of the repository) and
is mounted read-only into the containers. Nothing is downloaded at runtime.

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements/base.txt
.venv/bin/python -m app.retrieval.cli provision-model --path ../models/multilingual-e5-small-fd1525a
cd ..
```

### 2. Start the application

```bash
docker compose up -d --build backend frontend nginx
docker compose exec backend python -m app.retrieval.cli smoke-model   # optional model check
```

- Application: http://localhost:5173
- Through Nginx: http://localhost:8080
- API documentation: http://localhost:8000/docs

The backend checks at startup that the database schema matches the code and
refuses to start otherwise. Migrations are never run automatically: after
updating the code, back up the database and run the `migrate` command above
again.

### 3. Create a staff account

Register in the application, then give the account a role and sign in again:

```bash
docker compose exec backend python -m app.utils.manage_role you@example.com admin        # or researcher
```

### 4. Import the taxonomies

On the **Taxonomy** page (staff), upload the official release ZIP files with
their exact version:

- ESCO 1.2.1, classification, English, CSV (required)
- O*NET 29.0 TXT or O*NET 31.0 CSV (optional)
- ESCO–O*NET occupation mappings (optional)

The same imports are available as API endpoints (`POST /taxonomy/import/esco`,
`/onet`, `/mappings`). "Load development sample" loads a tiny sample release
for local testing only; it is not an official release.

### 5. Embed the ESCO occupation labels

Needed once per ESCO release, for the occupation suggestions in the work
experience form (about one minute on a laptop):

```bash
docker compose exec backend python -m app.retrieval.cli embed-occupation-labels
```

### 6. Import live jobs

Live jobs come from the public Arbeitnow API and the public Greenhouse job
boards listed in `GREENHOUSE_BOARDS`. Only English postings located in Europe
or remote are kept; contact details are removed before storage.

```bash
docker compose exec backend python -m app.job_sources.cli verify-sources     # check the Greenhouse boards
docker compose exec backend python -m app.job_sources.cli import-live-jobs   # fetch, process and embed
docker compose --profile scheduler up -d job-import                          # optional: repeat every 24 h
```

Administrators can also start an import with **Run import** on the Jobs page.
A first import of about 1,000 jobs takes a while (extraction, taxonomy linking
and embedding run for every job).

After each change, profiles and jobs are re-embedded automatically. For bulk
re-indexing (up to 1,000 per run; unchanged items are skipped):

```bash
docker compose exec backend python -m app.retrieval.cli index jobs --limit 1000
docker compose exec backend python -m app.retrieval.cli index profiles --limit 1000
```

To continue after 1,000 items, run the command again with `--after <next_after>`,
using the `next_after` value it printed.

After changing the job extraction rules, re-extract the stored live jobs. The
command is a dry run unless `--apply` is given. It adds new items, keeps every
reviewed item, and never touches the evaluation jobs. With
`--retire-unreviewed` it also removes items the current rules no longer find,
but only from live jobs and only if no person has reviewed them:

```bash
docker compose exec backend python -m app.services.job_service reextract                                # dry run
docker compose exec backend python -m app.services.job_service reextract --apply --retire-unreviewed
```

### Before a candidate sees results

A fresh installation shows no jobs until all of these are done:

| Step | Without it |
| --- | --- |
| Database migrated (`migrate`) | The backend does not start |
| Embedding model provisioned (step 1) | No profile or job can be embedded, so the Jobs page stays empty |
| ESCO 1.2.1 imported (step 4) | Skills are not linked to ESCO: no related skills, no occupations |
| Occupation labels embedded (step 5) | The work-experience form offers only name-based occupation suggestions |
| Jobs available (step 6, or jobs added by staff) | There is nothing to match |
| The candidate has confirmed skills or added skills | The profile is empty and cannot be matched |

## Demo account

The development database used for the screenshots has a synthetic candidate,
`demo.candidate@example.com` ("Alex Demo"), with a made-up CV and three work
entries. It contains no real personal data. The password is not published.
A fresh installation has no demo account: register a candidate account instead.

## Running the tests

Supported Python version: **3.12** (the version in the backend image). The
pinned PyTorch build is not available for newer Python versions; without it,
the tests that need the real model are skipped.

Backend tests (SQLite, no model needed):

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements/dev.txt
.venv/bin/python -m pytest -q
```

PostgreSQL tests use a separate, throw-away database that must be named
`skillgap_verify`:

```bash
docker run -d --rm --name skillgap-test-pg -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=skillgap_verify -p 55432:5432 pgvector/pgvector:pg16
TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:55432/skillgap_verify \
  .venv/bin/python -m pytest -q tests/test_retrieval_postgres.py tests/test_cv_lifecycle_postgres.py \
  tests/test_migration_check.py tests/test_taxonomy_postgres.py
docker stop skillgap-test-pg
```

Tests with the real embedding model run in Docker, with the provisioned model:

```bash
docker compose run --rm --no-deps \
  -v "$PWD/backend/tests:/app/tests:ro" -v "$PWD/backend/pytest.ini:/app/pytest.ini:ro" \
  -v "$PWD/backend/requirements:/app/requirements:ro" \
  -e REAL_MODEL_PATH=/models/multilingual-e5-small-fd1525a \
  backend sh -c "pip install -q -r requirements/dev.txt && python -m pytest -q tests/test_retrieval_real_model.py tests/test_representation_v2.py"
```

One of these also needs `TEST_DATABASE_URL` and is skipped without it.

Frontend tests and production build:

```bash
cd frontend
npm install
npm test
npm run build
```

## Environment variables

Set in `.env` (see `.env.example`); defaults are in `backend/app/core/config.py`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SECRET_KEY` | — | Signing key for login tokens. Set a long random value. |
| `DATABASE_URL` | `postgresql+psycopg://skillgap:skillgap@db:5432/skillgap` | Database connection |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `skillgap` | Database container credentials |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 | Refresh token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:8080` | Allowed frontend origins |
| `VITE_API_BASE_URL` | `http://localhost:8000` | API address used by the frontend |
| `RECOMMENDATION_TOP_N` | 100 | Jobs retrieved for the Jobs page |
| `AUTO_REINDEX` | true | Re-embed profiles and jobs after each change |
| `WARM_JOB_CACHE_ON_STARTUP` | true | Prepare job data in the background at startup |
| `LIVE_JOB_SOURCES` | `arbeitnow,greenhouse` | Live job sources |
| `GREENHOUSE_BOARDS` | 20 company boards | Greenhouse board names |
| `ARBEITNOW_MAX_PAGES` | 10 | Pages fetched from Arbeitnow per import |
| `LIVE_JOBS_MAX_ACTIVE` | 1500 | Maximum active live jobs |
| `LIVE_JOBS_MAX_SOURCE_SHARE` | 0.7 | Maximum share of that limit per source (1.0 = no limit) |
| `LIVE_JOBS_ARCHIVE_AFTER_DAYS` | 14 | Archive live jobs not seen for this many days |
| `LIVE_JOBS_ENGLISH_ONLY` | true | Keep English postings only |
| `LIVE_JOBS_EUROPE_OR_REMOTE_ONLY` | true | Keep postings in Europe or remote only |
| `LIVE_JOB_IMPORT_INTERVAL_SECONDS` | 86400 | Interval of the optional scheduled import |
| `CANDIDATE_VIEW_INCLUDES_EVALUATION_JOBS` | false | Show the fixed evaluation jobs to candidates |
| `JOB_EXTRACTION_ESCO_VOCABULARY` | true | Use ESCO skill labels when extracting job skills |
| `JOB_EXTRACTION_VERSION` | v4 | Job skill extraction rules: `v4` adds list splitting, language and named-certification rules and filters for generic terms and company, benefits and equal-opportunity text; `v3` is the previous rule set. CVs are not affected |

## Documentation

- [Architecture](docs/architecture.md)
- [Design decisions](docs/design-decisions.md)
- [Evaluation](docs/evaluation.md)
- [Privacy](docs/privacy.md)
- [User guide](docs/user-guide.md)

## Data sources and attribution

**ESCO.** This service uses the ESCO classification of the European
Commission. ESCO v1.2.1 (classification, English) is reused under Commission
Decision 2011/833/EU on the reuse of Commission documents
(https://esco.ec.europa.eu/en/about-esco/faq). ESCO data is imported into a
local database and, for the occupation suggestions, converted into embedding
vectors. The test fixtures in `backend/tests/fixtures/taxonomy/esco/` contain
modified, abridged excerpts of ESCO files.

**O\*NET.** This application can import, and its test fixtures include
information from, the O\*NET® 29.0 Database and the O\*NET® 31.0 Database by
the U.S. Department of Labor, Employment and Training Administration
(USDOL/ETA). Used under the [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
license. O\*NET® is a trademark of USDOL/ETA. The authors of this project have
modified all or some of this information (subset selection and JSON
serialization for the test fixtures; import into a local database).
USDOL/ETA has not approved, endorsed, or tested these modifications.
Source: https://www.onetcenter.org/database.html, licence:
https://www.onetcenter.org/license_db.html.

**Embedding model.** `intfloat/multilingual-e5-small`, MIT license, downloaded
separately (not included in this repository).

**Job postings.** Live jobs come from the public Arbeitnow job board API and
public Greenhouse job boards; each job links to its original posting. Test
fixtures for these sources use synthetic titles, companies, people and texts.

## Limitations

- Scanned PDFs are not supported (no OCR).
- CV skill extraction uses a small curated dictionary; job extraction also uses
  ESCO skill labels. Candidates may need to add skills by hand.
- The retrieval evaluation is small (8 candidate profiles, 30 jobs, one rater).
- There is no export of a candidate's own data, and no automatic expiry of
  inactive accounts.

## License

The source code is released under the MIT License, see [LICENSE](LICENSE).
Third-party data keeps its own terms (see Data sources and attribution).
