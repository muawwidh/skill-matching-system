# Phase 5 Template V2 Follow-Up Verification

Date: 2026-11-04. Base HEAD: `8607310aa12bec4e338f2d017bab48bec23c3426`.
Uncommitted follow-up; no indexing, real-model encoding, rankings, deployment
or human relevance judgments occurred. Existing synthetic unit/PG tests use
fake vectors only. V1 remains the baseline and Phase 5 remains incomplete.

## Classification Correction

- `Desired Skills` and `Desired Qualifications` are preferred aliases, using
  existing case/colon/question-mark handling.
- Recognized headings supply the default class. A preference cue overrides an
  explicit heading only when the whole original line is clearly optional.
- Parenthetical/bracketed cues alone do not make a line optional. Mandatory
  wording, multiple sentences and subordinate preference clauses retain the
  explicit heading class. Mixed requirements are not rewritten into invented
  semantic fragments. Ordinary source-unit selection preserves wording.
- Clear leading preferred markers and
  whole-line preferred predicates can classify a line as preferred; bare endings
  alone remain ambiguous and cannot override the heading.
- Budget caps/weights are unchanged; no job IDs, company names, candidate
  families or relevance labels drive selection. Unreleased v2 stays v2.

## Corrected J12 Explanation

The earlier J12 issue was classification, not token-budget truncation. Missing
desired-section aliases and an overly broad preference cue put source lines in
the wrong classes. Previously only one preferred source unit survived. J12 now
retains ten preferred source units; its recorded desired-skill block has
representative overlap of at least twelve consecutive source words. The mixed
required-experience line keeps its required section class. Stored skill
classifications, extraction reviews and taxonomy selections are unchanged.
Selection remains representative, not exhaustive.

`before`: `9b364b6c8074fba3bd1dac38ca45db13f26e94a14202fcb66db4cbea71ed76bf`
`after`: `ec6d18ac6a22e456f9a0442167a3683f3bcce1e9a008d10b580ad8762e2627c5`

## Per-Job Dry Run

All 30 recorded v1 hashes are unchanged. Every v2 output is deterministic and
at most 512 tokens including special tokens (observed 503-508). Every selected
source fragment was verified as an exact prefix of its whitespace-normalized
stored unit; rendered source classes were checked against those fragments.
No restricted source/candidate text is reproduced. R/P/D counts retained
requirement/preference/responsibility source units, not approved skills.
No recognized substantive class is lost. The JSON records each job's v1 hash,
v2 before/after hashes, source hash, fallback, source overlap and verbatim check.

| Job | Tokens | R/P/D Units | Structured Occurrences | Fallback | Verbatim |
|---|---:|---|---|---|---|
| J01 | 508 | 16/7/8 | unknown:2 | stored/headings | yes |
| J02 | 503 | 4/0/22 | none | stored/headings | yes |
| J03 | 508 | 20/0/16 | unknown:1 | stored/headings | yes |
| J04 | 508 | 19/0/12 | none | stored/headings | yes |
| J05 | 508 | 13/0/13 | none | stored/headings | yes |
| J06 | 508 | 4/1/2 | none | line-cues+stratified-context | yes |
| J07 | 508 | 9/4/8 | required:2, preferred:1 | stored/headings | yes |
| J08 | 508 | 11/8/17 | required:2, unknown:2 | stored/headings | yes |
| J09 | 508 | 9/0/21 | unknown:1 | stored/headings | yes |
| J10 | 508 | 6/0/2 | unknown:2 | line-cues+stratified-context | yes |
| J11 | 508 | 17/0/18 | unknown:13 | stored/headings | yes |
| J12 | 508 | 13/10/14 | required:1 | stored/headings | yes |
| J13 | 508 | 23/0/10 | unknown:2 | stored/headings | yes |
| J14 | 508 | 23/11/22 | unknown:3, preferred:1 | stored/headings | yes |
| J15 | 508 | 20/13/19 | preferred:1, required:2 | stored/headings | yes |
| J16 | 508 | 4/1/6 | unknown:4 | stored/headings | yes |
| J17 | 508 | 14/1/14 | unknown:5 | stored/headings | yes |
| J18 | 508 | 17/1/20 | required:2 | stored/headings | yes |
| J19 | 508 | 18/0/17 | unknown:1 | stored/headings | yes |
| J20 | 508 | 15/2/15 | unknown:3 | stored/headings | yes |
| J21 | 508 | 11/6/14 | unknown:1, preferred:1 | stored/headings | yes |
| J22 | 508 | 7/16/1 | preferred:1, unknown:1 | stored/headings | yes |
| J23 | 508 | 10/8/12 | unknown:6, preferred:3 | stored/headings | yes |
| J24 | 508 | 3/0/24 | unknown:4 | stored/headings | yes |
| J25 | 508 | 17/0/16 | none | stored/headings | yes |
| J26 | 508 | 17/0/15 | unknown:7 | stored/headings | yes |
| J27 | 508 | 15/0/20 | unknown:7 | stored/headings | yes |
| J28 | 508 | 15/0/14 | unknown:2 | stored/headings | yes |
| J29 | 508 | 15/0/13 | unknown:3 | stored/headings | yes |
| J30 | 508 | 15/1/12 | unknown:5 | stored/headings | yes |

## Verification

- Focused tests with private corpus: 77 passed, 3 pinned-tokenizer skips;
  those gates passed separately with the actual pinned tokenizer.
- Complete default suite: 270 passed, 51 environment-gated skips.
- Complete isolated PostgreSQL suite: 315 passed, 6 gated skips.
- Pinned offline tokenizer/model-load-only and persistence gates: 36 passed,
  0 skipped. No real-model encode call was made.
- Existing real-vector gate was not rerun under the no-encode boundary;
  historical real-model evidence is unchanged.
- All five mutations were caught: one-template invalidation; disabled oversize
  shrinking; unnecessary exact-512 shrinking; subordinate preferred override;
  missing desired aliases. Child-process memory mutations never edited source.
- Pinned-tokenizer tests deliberately overallocate a first draft to exercise
  shrinking and separately preserve an exactly-512 draft without removal.
- HEAD v1 candidate/job byte/hash goldens were captured from the base commit.
- Fresh PG sessions confirm invalidation stales coexisting v1/v2 profile/job
  rows while preserving vector/hash metadata.
- Diff checks include tracked and untracked sources. Frontend is unchanged;
  no frontend build, migration or repository dependency change was needed.

## Safeguards and Hashes

Developer state remains 42 jobs, 92 pending evaluation skills and zero rows
in both embedding tables. All original/imported job rows, frozen candidate
inputs and 121 local input files are unchanged. The final dry rerun used mapped
job reads and requested aggregates only, not CV/candidate/audit-table queries;
frozen candidate inputs were verified at the earlier read-only checkpoint.
No API write was made.
Repository/isolated/developer heads remain `0008_dense_retrieval`.
Disposable tmpfs PostgreSQL/network were removed; normal container IDs/start
times are unchanged. Test tools existed only in disposable tmpfs.

The JSON records policy before/after hashes, each job's v2 before/after hash,
previous report hashes, the initial tree hash, implementation hashes and the
complete file list. Report self-hashes are provided separately at completion.

## Complete Uncommitted File List

- `backend/app/api/routes/retrieval.py`
- `backend/app/core/config.py`
- `backend/app/repositories/retrieval_repository.py`
- `backend/app/retrieval/benchmark.py`
- `backend/app/retrieval/cli.py`
- `backend/app/retrieval/embedder.py`
- `backend/app/retrieval/job_budget.py`
- `backend/app/retrieval/representation.py`
- `backend/app/services/retrieval_service.py`
- `backend/tests/conftest.py`
- `backend/tests/test_representation_v2.py`
- `backend/tests/test_retrieval_benchmark.py`
- `backend/tests/test_retrieval_postgres.py`
- `backend/tests/test_retrieval_real_model.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`
- `docs/architecture.md`
- `docs/phase5-dense-retrieval.md`
- `docs/processing-flow.md`
- `docs/verification/phase5-template-v2.json`
- `docs/verification/phase5-template-v2.md`

Only the nine JSON `followup_changed_files` changed during this follow-up;
the remaining accepted v2 changes are preserved byte-for-byte.
