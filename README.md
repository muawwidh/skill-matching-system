# Skill Gap Job Matching System

A modular full-stack research application for explainable skill gap analysis and job recommendations.
The system is designed for career guidance and decision support, not automated hiring decisions.

This repository currently implements Phases 1 through 3 from the requirements, together with an
early exact-skill matching baseline that will be expanded during Phase 6.

Phase 1 includes foundation, Docker setup, PostgreSQL setup, backend app shell, frontend app shell,
configuration management, authentication, role-based access, database connection, Alembic migration,
and setup documentation.

Phase 2 adds CV upload, CV paste input, job creation, PDF/DOCX/TXT parsing, MIME and size validation,
text cleaning, section extraction, and processing logs.

Phase 3 adds dictionary and regex-based extraction for skills, tools, technologies, qualifications,
occupations, and experience indicators. The extractor includes an optional spaCy PhraseMatcher path
when spaCy is installed, while the default Docker build stays lightweight and reproducible.

The early matching baseline compares reviewed candidate and job skills, stores match results, and
shows required and preferred skill gaps. Taxonomy-aware, semantic, weighted matching remains part of
the later taxonomy, dense retrieval, and matching phases.

## Architecture

Frontend -> API routes -> Services -> Repositories -> Database / NLP / Matching / Taxonomy modules.

See:

- `docs/architecture.md`
- `docs/database-erd.md`
- `docs/processing-flow.md`
- `docs/privacy.md`

## Technology Stack

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn
- Database: PostgreSQL with pgvector image support
- Frontend: React, TypeScript, Vite, Tailwind CSS, React Query, React Hook Form
- Document parsing: pypdf, python-docx, TXT decoding
- NLP baseline: local dictionaries, spaCy PhraseMatcher where available, regex patterns
- Deployment: Docker Compose and Nginx
- Tests: pytest and FastAPI TestClient

## Setup

Create an environment file:

```bash
cp .env.example .env
```

Start the system:

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:5173`
- Nginx proxy: `http://localhost:8080`
- FastAPI docs: `http://localhost:8000/docs`

## Database Migrations

The backend container runs migrations at startup. To run them manually:

```bash
cd backend
alembic upgrade head
```

## Local Backend Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
uvicorn app.main:app --reload
```

## Local Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
cd backend
pip install -r requirements/dev.txt
pytest
```

## Environment Variables

Key variables are documented in `.env.example`.

- `DATABASE_URL`: SQLAlchemy connection string.
- `SECRET_KEY`: JWT signing secret. Replace before production.
- `CORS_ORIGINS`: comma-separated allowed frontend origins.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: access-token lifetime.
- `REFRESH_TOKEN_EXPIRE_DAYS`: refresh-token lifetime.

## API Documentation

FastAPI exposes OpenAPI documentation at `/docs`.

Implemented Phase 1 endpoints:

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

Implemented Phase 2 endpoints:

- `GET /candidates/me`
- `PUT /candidates/me`
- `POST /cvs/upload`
- `POST /cvs/paste`
- `GET /cvs`
- `GET /cvs/{document_id}`
- `DELETE /cvs/{document_id}`
- `POST /cvs/{document_id}/process`
- `GET /cvs/{document_id}/sections`
- `GET /cvs/{document_id}/extracted-skills`
- `PUT /cvs/{document_id}/extracted-skills`
- `POST /jobs`
- `POST /jobs/import`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `PUT /jobs/{job_id}`
- `DELETE /jobs/{job_id}`
- `POST /jobs/{job_id}/process`
- `POST /jobs/{job_id}/archive`
- `GET /jobs/{job_id}/sections`
- `GET /jobs/{job_id}/extracted-skills`
- `PUT /jobs/{job_id}/extracted-skills/{skill_id}`
- `GET /admin/logs`
- `GET /matches/recommendations`
- `POST /matches/recommendations/refresh`
- `POST /matches/jobs/{job_id}`

## Known Limitations

Phases 1, 2, and 3 are implemented. An early exact-skill matching baseline is also available.
Taxonomy import, dense retrieval, complete weighted matching, evaluation, and candidate data deletion
are prepared as clean module boundaries and should be implemented in later phases.

## Future Improvements

1. Phase 4: local ESCO/O*NET import and taxonomy linking.
2. Phase 5: embeddings and vector retrieval.
3. Phase 6: weighted matching and skill gap explanations.
4. Phase 7: recommendation experience.
5. Phase 8: evaluation metrics and export.
6. Phase 9: privacy controls, retention, audit logs, and production deployment hardening.
