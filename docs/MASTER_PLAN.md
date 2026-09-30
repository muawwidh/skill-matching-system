# Master Development Plan

## Project

Development and Evaluation of an Explainable Skill-Gap Job Matching System
Using ESCO/O*NET Taxonomies and Dense Retrieval

## Goal

Develop and evaluate a full-stack application that:

- processes CVs and job descriptions
- extracts structured skills
- normalizes skills using ESCO and O*NET
- retrieves semantically relevant jobs
- calculates transparent match scores
- identifies skill gaps
- provides evidence-backed explanations
- supports Candidate and Administrator/Researcher workflows
- supports reproducible Bachelor thesis evaluation

## Phase 1 — Foundation

- repository structure
- Docker
- PostgreSQL
- FastAPI
- React frontend
- configuration
- authentication
- RBAC foundation
- SQLAlchemy
- Alembic
- health/API setup
- documentation
- tests

## Phase 2 — Document Processing

- candidate profiles
- CV upload/paste
- PDF/DOCX/TXT parsing
- validation
- text cleaning
- PDF normalization
- CV sections
- job creation/import
- job sections
- processing logs
- processing persistence

## Phase 3 — Skill Extraction

- skill dictionary
- dictionary/rule extraction
- regex extraction
- extracted candidate terms
- extracted job terms
- evidence
- confidence scores
- candidate skills
- job skills
- skill review/correction
- approve/reject workflow

## Phase 4 — Taxonomy Integration

- versioned ESCO storage
- versioned O*NET storage
- concepts
- labels
- relationships
- O*NET-SOC occupations
- occupation information
- ESCO–O*NET mappings
- official taxonomy import
- development samples
- taxonomy search/details
- exact linking
- alternative-label linking
- normalized linking
- fuzzy linking
- ranked candidates
- confidence scoring
- high-confidence automatic approval
- researcher/admin review
- automatic CV/job taxonomy linking

## Phase 5 — Dense Retrieval

- embedding service abstraction
- Sentence Transformer integration
- model/version metadata
- candidate/profile embeddings
- job embeddings
- PostgreSQL pgvector where available
- vector-store abstraction/fallback
- top-N semantic job retrieval

Dense retrieval is first-stage candidate retrieval.

It is not the final match score.

## Phase 6 — Matching and Skill-Gap Analysis

- detailed scoring engine
- configurable/versioned scoring
- semantic similarity
- required skill coverage
- preferred skill coverage
- occupation alignment
- qualification/experience alignment
- critical-skill penalty
- Matched classification
- Partially Covered classification
- Missing classification
- taxonomy-aware relationships
- evidence-backed explanations

Initial intended scoring configuration:

- 0.35 semantic similarity
- 0.35 required skill coverage
- 0.15 preferred skill coverage
- 0.10 occupation alignment
- 0.05 qualification/experience alignment
- critical-skill penalty where applicable

Weights must remain configurable/versioned.

## Phase 7 — Recommendation Experience

- recommendation list
- recommendation detail
- score breakdown
- skill-gap display
- evidence
- explanations
- save
- dismiss
- compare
- candidate development areas

## Phase 8 — Evaluation

Ranking:

- Precision@K
- Recall@K
- MRR
- nDCG@K

Skill extraction:

- precision
- recall
- F1

Taxonomy linking:

- accuracy
- top-K accuracy
- confidence/calibration

Skill-gap analysis:

- gap correctness
- matched/partial/missing quality

Explainability:

- evidence support
- clarity
- consistency
- human review

Record for reproducibility:

- taxonomy version
- embedding model/version
- scoring version
- dataset version

## Phase 9 — Security, Privacy and Deployment

- candidate data deletion
- consent
- retention
- RBAC hardening
- restricted file access
- audit/log improvements
- GDPR considerations
- production configuration
- health/deployment hardening
- final documentation

## Candidate Final Capabilities

- register/login
- manage profile
- upload/paste CV
- inspect processed information
- review/correct skills
- receive job recommendations
- inspect scores
- inspect skill gaps
- inspect evidence/explanations
- save/dismiss jobs
- compare jobs
- delete personal/uploaded data

## Administrator / Researcher Final Capabilities

- manage jobs
- bulk import jobs
- review extraction
- required/preferred skill classification
- import/manage taxonomy releases
- review taxonomy mappings
- manage scoring configurations
- inspect model/taxonomy versions
- run evaluations
- export evaluation results
- inspect logs/errors

## Core Principle

Explanations must be grounded in stored structured evidence.

This system supports career decision-making and is not an automated
candidate-selection system.