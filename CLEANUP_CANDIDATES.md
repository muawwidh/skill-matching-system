# Cleanup Candidates

Files that look unused, duplicated, old or experimental. **Nothing has been
deleted or moved.** Each entry is a candidate for you to decide on, not a
recommendation to delete. "Unreferenced" was checked by scanning imports in
`frontend/src`, `frontend/tests` and `backend/`, plus the Dockerfiles, compose
file, README and docs.

Overall the tracked code is tidy: every frontend source file is imported
somewhere, and every backend module is imported, run by Docker, or documented
as a command-line script. Most candidates below are local leftovers or
deliberately kept legacy code.

## 1. Duplicates

| Path | Reason | Notes |
|---|---|---|
| `data/sample/skill_dictionary.json` | Byte-identical to `backend/app/nlp/skill_dictionary.json`. The extractor loads only the copy next to `skill_extractor.py`; no code reads this one. | Keeping two copies risks them drifting apart. Check whether any doc or script expects it under `/data/sample` first. |

## 2. Legacy code that is still wired in

These are old, but still reachable from the app, so they are not dead code.
`docs/PROJECT_STATE.md` says the legacy matcher is kept on purpose as
"prototype behavior".

| Path | Reason |
|---|---|
| `backend/app/services/matching_service.py` | Early exact-skill matcher, replaced in purpose by the Phase 6 `matching_runs_service.py`. |
| `backend/app/api/routes/matches.py` | `/matches` endpoints serving the legacy matcher. |
| `frontend/src/components/JobMatchPanel.tsx` | UI for legacy matches. |
| Legacy match calls in `frontend/src/api/documents.ts` and the "Load legacy prototype recommendations" button in `frontend/src/pages/JobsPage.tsx` | Front-end entry to the legacy matcher. |
| `backend/app/db/migrations/versions/0004_candidate_job_matching.py` | Creates the legacy match tables. **Never delete an applied migration**; listed only for context. |

Removing the legacy path would be a design decision (and needs a new
migration to drop its tables), not a cleanup.

## 3. Empty placeholders

| Path | Reason |
|---|---|
| `backend/app/workers/__init__.py` | Only a docstring ("Background worker entry points"); nothing imports it. |
| `backend/app/evaluation/__init__.py` | Only a docstring ("Evaluation interfaces for later phases"); nothing imports it. Evaluation code actually lives in `backend/app/retrieval/`. |
| `frontend/src/hooks/.gitkeep`, `frontend/src/utils/.gitkeep` | Empty folders kept by `.gitkeep`. |
| `data/evaluation/.gitkeep`, `data/taxonomy/.gitkeep` | Empty folders; `data/` is mounted into the backend as `/data`, so they may be expected at runtime (?). |

## 4. One-off scripts (not referenced by the running app)

| Path | Reason |
|---|---|
| `backend/scripts/verify_phase5_real.py` | One-shot Phase 5 evidence run. Not imported, not mentioned in README or docs by file name. Its output is recorded in `docs/verification/phase5-real-*`. Probably worth keeping as the reproducibility record (?). |
| `backend/app/scripts/verify_onet31.py`, `verify_taxonomy_package.py` | Phase 4 verification tools, referenced only from `docs/phase4-verification.md` and `docs/onet-31-contract.md`. Keep if you want the verification to stay reproducible. |
| `backend/app/utils/manage_role.py` | CLI only (documented in README). Not dead; listed because nothing imports it. |

## 5. Local leftovers in the project folder (git-ignored, not in the repository)

These are large or sensitive local files sitting in the project root. They are
ignored by git, so they don't affect the repository, but they clutter the
folder.

| Path | Reason |
|---|---|
| `phase4-before-upgrade-20261001-180512.dump`, `phase4-before-upgrade-0007-20261001-190905.dump`, `phase4-before-onet31-runtime-20261002-082407.dump` | Database backups from before the Phase 4 upgrades (early October). Likely superseded by later backups, but they are your only copy of that state (?). Consider moving them out of the project folder rather than deleting. |
| `esco-1.2.1-en.zip` and `ESCO dataset - v1.2.1 - classification - en - csv/` | The same ESCO release twice: once zipped, once unpacked. The importer takes the ZIP, so the unpacked folder may be unnecessary (?). |
| `db_31_0_csv.zip` | O\*NET 31.0 package used for import/verification. Needed only to re-import. |
| `.DS_Store` files (root, `evaluation/local/`, elsewhere) | macOS Finder metadata; ignored by git. Safe clutter. |
| `evaluation/local/__pycache__/` | Python cache inside the private evaluation folder, meaning helper scripts were run from there. |

## 6. Private evaluation folder (review carefully, do not bulk-delete)

`evaluation/local/` (git-ignored) holds the private evaluation corpus and the
evidence trail: freeze plans, applied/final/verification files, deployment and
migration records, pre-migration backups, timestamped run folders, and a few
helper scripts. Many files come in families such as `*-plan`, `*-preview`,
`*-applied`, `*-final`, `*-verification`, or `*-blocked`, and some deployment
records exist in both a first and a `-final` version.

These look like duplicates or old versions, but several are hash-pinned by
later records and project docs (for example the representability audit and
review packet list exact SHA-256 values of their source files). Deleting or
editing any of them can break those audit trails. Treat this folder as an
archive; if you want it tidier, decide per family which file is authoritative
and move superseded ones to an archive folder outside the project.

It also contains credential files for evaluation accounts. Those should stay
out of the repository (they are ignored) and ideally live somewhere outside
the project folder.

## 7. Work in progress (not clutter, but worth knowing)

| Path | Reason |
|---|---|
| `frontend/src/components/matching/CandidateFactsPanel.tsx`, `JobSkillReview.tsx`, `ReviewSummary.tsx` | New, uncommitted files. They are imported by modified pages, so they are in use, but they aren't in git yet. If they're wanted, commit them; if they're an abandoned experiment, the page changes that import them are too. |
| Uncommitted edits to tracked files (`backend/app/retrieval/embedder.py`, several frontend pages, `styles.css`, frontend tests, `tsconfig.json`) | Unfinished changes in the working tree. The list grew while this inventory was being written (2026-11-18), so another session appears to be actively editing. |
