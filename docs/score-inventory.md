# Score and Constant Inventory

Snapshot of the repository at commit `349e668` (branch `simple-matching`),
compiled 2026-11-18 by reading the code. No code was changed to produce it.
Section 1 and the display notes in sections 3 and 5 were updated on
2026-11-18 for D036, and section 1 again for D040.

Scope: every numeric value that is shown to a user or persisted as a result,
plus every threshold, weight, cut-off or budget that determines one of those
values. Paths are relative to `backend/app/` unless stated otherwise.

## Origin categories

| Category | Meaning |
|---|---|
| **Data-derived** | Fitted, calibrated or measured from project data. |
| **Source** | Taken from an external specification: the model card or architecture, a library's definition, or a standard formula from the literature. |
| **Arbitrary** | Hand-chosen by the developer. "Documented" means the value and its intent are recorded in `docs/DECISIONS.md` or another doc. That record gives no empirical justification, so the value stays arbitrary. |

**Main finding:** no constant in the scoring, extraction, linking or retrieval
paths is data-derived. Every hand-set threshold and weight is arbitrary. Only
the model-imposed limits and the standard metric formulas come from a source.
The only data-derived numbers are evaluation **outputs** (section 6).

---

## 1. Skill coverage matcher (`/matches`, transitional Phase 6 prototype)

Replaced on 2026-11-18 by D036. The former 2:1 weighted percentage, the
`unknown`→required rule and the 80/50 explanation cut-offs no longer exist.
They are listed under "Removed" below.

Shown to users in `JobsPage` → `frontend/src/components/JobMatchPanel.tsx`
("Skill coverage"). Persisted in `candidate_job_matches`. Rows are recomputed
on every `GET /matches/recommendations`.

| Value | Where computed | Exact rule | Constants | Origin |
|---|---|---|---|---|
| Eligible skills | `repositories/document_repository.py:506,518` `list_matchable_*_skills` | `review_status == "approved"` on both sides | — | Methodological choice, documented (D036) |
| | `services/matching_service.py:20` | Compared only if `skill_type ∈ SKILL_LIKE_TYPES`. Other approved job terms are listed as "not assessed". | `{skill, tool, domain_knowledge, language}` | Arbitrary, documented (D036) |
| Concept for a skill | `document_repository.py:524` `approved_skill_concepts` | Approved link on an **active** release, kept only if the skill text still equals its extracted term (same rule as retrieval) | — | Reuses the Phase 4/5 rule |
| Matched / missing | `matching_service.py` `compute_coverage` | Job skills are grouped by concept (or by name if unlinked). A linked group is matched `taxonomy_concept` if any candidate concept is equal; else matched `skill_name` if an **unlinked** candidate skill has the same name; else missing with `checked_via = taxonomy_concept`. An unlinked group is matched `skill_name` if any candidate skill has the same name; else missing with `checked_via = skill_name`. Every compared group counts in the totals. | — | Methodological choice, documented (D036, D040) |
| Requirement class | `_job_groups` l.66 | `unknown` → preferred. Required wins if the same skill is listed both ways. | — | Methodological choice, documented (D036) |
| "Required skills: X of Y matched" | frontend from `matched_required`, `missing_required` | `X = |matched_required|`, `Y = X + |missing_required|` | — | Count |
| "Preferred skills: X of Y" | as above, preferred lists | as above | — | Count |
| Chip tooltips | `JobMatchPanel.tsx` | Covered: `matched_via` → "Matched via taxonomy concept" / "Matched by same skill name". Missing: `checked_via` → "Not found in your CV by taxonomy concept or name" / "Not found in your CV by name (may appear under a different wording)" | — | — |
| `explanation` | `matching_service.py` `build_explanation` | Lines built only from the lists: required line, preferred line, "Checked by name only (may appear in your CV under a different wording): …", "Also required/preferred — not assessed by the system: …" | — | No thresholds |
| Ranking (response order and "#N of M") | `MatchingService.list_my_recommendations` | Since D045: the top-N jobs returned by `RetrievalService.retrieve` (exact cosine, ties by job ID), in that order. Jobs without a current vector are not retrieved. Coverage does not affect the order. | `RECOMMENDATION_TOP_N = 50` (`core/config.py`) | N: Arbitrary, documented (D045). No weights |
| Similarity | `RetrievalService.retrieve` | Only orders the retrieved jobs. Never returned by `/matches` or displayed. | — | See section 2 |
| Former coverage order (offline only) | `matching_service.py` `coverage_ranking_key` | Lexicographic: (no required skills → last; required coverage desc as an exact `Fraction`; no preferred skills → after; preferred coverage desc; matched required count desc; matched preferred count desc; similarity missing → after; similarity desc; job ID). Used only by `compare-matching` variants B–D. | — | App order until D044 (D036, D040, D043) |
| `score` (stored, **not displayed**) | `matching_service.py:278` | `round(100 · |matched_required| / Y_required, 2)`, or `0.0` if `Y_required = 0` | `100`, `2` d.p. | Legacy column kept without migration; not used for ranking |
| `candidate_skill_count` | `compute_coverage` | Number of approved skill-like candidate skills | — | Count |
| `job_skill_count` | `_score_job` | `Y_required + Y_preferred` (all skill-like groups) | — | Count |

No constant in this section is a tuned threshold or weight. The remaining
choices (type set, eligibility, `unknown`→preferred) are methodological
rules recorded in D036. The order is retrieval similarity (D044).

Removed (for traceability): `required_weight = 2` and `preferred_weight = 1`;
`unknown` counted as required; the `{skill, tool}` type filter; inclusion of
pending skills; explanation cut-offs `80`/`50`; the `Math.round(score)%`
display; the "could not be compared" exclusion of unlinked job skills (D040).

---

## 2. Dense retrieval (`GET /retrieval/jobs`, Phase 5)

Returned by the API but **not shown in any frontend page**. Since D044 it is
the order of the Jobs page and of "#N of M" (section 1). The similarity value
itself is never displayed.
Ranking is not persisted. The embeddings are persisted in `job_embeddings` and
`candidate_profile_embeddings`.

| Value | Where computed | Exact formula | Constants | Origin |
|---|---|---|---|---|
| `retrieval_similarity` | `services/retrieval_service.py:94` `RetrievalService.jobs_for_user`. The distance comes from `repositories/retrieval_repository.py:139` `exact_jobs`. | `1.0 − cosine_distance(q, d)`, where pgvector computes `cosine_distance = 1 − (q·d)/(‖q‖‖d‖)`. Vectors are L2-normalised at encode time, so the result equals `q·d`. Search is an exact scan ordered by `(distance, job.id)`. | Cosine as the similarity measure | Source (E5 usage convention) |
| `rank` | `jobs_for_user` | 1-based position after the exact sort. Jobs whose stored `source_hash` is stale are skipped. | — | — |
| Query and passage embeddings | `retrieval/embedder.py:43` `LocalE5Embedder.encode` | `SentenceTransformer.encode(bounded_text, normalize_embeddings=True)`. Mean pooling is set by the model's `1_Pooling` config. | Model `intfloat/multilingual-e5-small` @ `fd1525a9…` | Source (pinned model) |
| | | | `DIMENSION = 384` (`retrieval/representation.py:12`) | Source (model architecture) |
| | | | `MAX_TOKENS = 512` (l.13), including 2 special tokens | Source (model max sequence length) |
| | | | Prefixes `"query: "` / `"passage: "` (l.45, l.54) | Source (E5 model card) |
| `limit` default / maximum | `api/routes/retrieval.py:16` | `Query(20, ge=1, le=100)` | 20, 1, 100 | Arbitrary |
| Internal page size | `retrieval_service.py:85` | Fetches 100 rows per scan page | 100 | Arbitrary (performance only, does not affect results) |

Observed similarities are tightly packed. For two real accounts on 2026-11-18,
the top-5 values were 0.84–0.88. The values are not calibrated probabilities.
Per AGENTS.md they must not be used as the final match score.

### 2a. Job representation budget (template `e5-job-profile-v2`)

These constants decide **what text is embedded**, so they shape every
`retrieval_similarity`. The algorithm lives in `retrieval/job_budget.py`
`budget_job` (l.241). It is recorded as predeclared in DECISIONS.md D030.

| Constant | Location | Role | Origin |
|---|---|---|---|
| `METADATA_CAP = 104` tokens | l.7, `_metadata` | Hard cap for the title, employment and location block | Arbitrary, documented (D030) |
| Per-field caps `60 / 12 / 12` (title/employment/location) | l.112 | Starting clip lengths. The largest cap is reduced by 1 until the block fits `METADATA_CAP`. | Arbitrary, undocumented |
| `STRUCTURED_CAP = 96` tokens | l.8, `_structured` | Cap for the required, preferred and other skill lists | Arbitrary, documented (D030) |
| `STRUCTURED_CAP − 6` | l.136 | Reserve for line separators | Arbitrary, undocumented |
| Structured weights `required 3 : preferred 2 : unknown 1` | l.136 | Split of the structured cap | Arbitrary, undocumented |
| `CLASS_WEIGHTS` `requirements 4, preferences 2, responsibilities 4, summary 1, context 1` | l.9 | Split of the remaining tokens across verbatim source classes | Arbitrary, documented (D030) |
| `_allocate` | l.101 | `quota_k = ⌊total·w_k/Σw⌋`. Leftover units go +1 each to the first keys in insertion order. | Algorithm choice |
| Safety margin `−12`, then `−2` for special tokens | l.249 | `budget = 512 − 2 − tokens(metadata+structured) − 12` | `2`: Source (tokenizer contract). `12`: Arbitrary |
| `−3` per bucket label | l.213 | Reserve inside each class bucket | Arbitrary |
| Refund: `spare = 512 − size − 4`, stop if `spare < 8` | l.272, l.275 | Spends unused tokens on unfinished classes | Arbitrary |
| Shrink step `size − 512 + 2` | l.286 | Reduces the budget after an over-length render | Arbitrary |
| Unit chunking `64` words | l.182 | Long sentences are split into 64-word units | Arbitrary |
| Stratified anchors: first, middle (`(n−1)//2`), last unit | `_render_bucket` l.211 | Picks which snippets are kept first | Arbitrary |

Template v1 (`job_representation`, `retrieval/representation.py`) has no budget
constants. It truncates the full text at 512 tokens through `bounded_text`
(l.69). The candidate text is the same in v1 and v2: approved skills,
canonical labels and evidence. Only `review_status == "approved"` skills are
included. Pending skills are excluded, unlike the legacy matcher.

---

## 3. Skill extraction confidence (Phase 3)

Persisted on extracted terms, `candidate_skills` and `job_skills`, and returned
by the API. **No longer displayed** since 2026-11-18. `SkillReviewPanel` and
`CandidateSkillGroups` now show the skill's `source` ("extracted" / "manual")
instead of the former `Math.round(confidence_score*100)%`.

| Value | Where computed | Formula | Constant | Origin |
|---|---|---|---|---|
| Dictionary match (regex fallback) | `nlp/skill_extractor.py:121` | Fixed value | `0.90` | Arbitrary, undocumented |
| spaCy PhraseMatcher dictionary match | l.149 | Fixed value | `0.92` | Arbitrary, undocumented |
| Regex `experience_indicator` ("N years experience") | l.165 | Fixed value | `0.86` | Arbitrary, undocumented |
| Regex `qualification` (bachelor/master/…) | l.166 | Fixed value | `0.82` | Arbitrary, undocumented |
| Regex `certification` | l.167 | Fixed value | `0.78` | Arbitrary, undocumented |
| Deduplication | `_deduplicate` l.234 | Keeps the highest-confidence term per `(normalized_text, term_type, source_section)` | — | Algorithm choice |
| Evidence list-item split | `_evidence_sentence` | Uses list-fragment evidence if the sentence is longer than `140` chars or contains `≥ 2` delimiters | `140`, `2` | Arbitrary, undocumented |

These are constant labels per extraction method, not per-match
probabilities. Nothing reads them in scoring or retrieval. That is why they
are no longer displayed as percentages.

## 4. Section detection confidence (Phase 2)

Persisted on `cv_sections` and `job_sections`, and returned by the API. It is
not rendered in the UI.

| Value | Where | Formula | Constant | Origin |
|---|---|---|---|---|
| Heading-matched section | `services/section_detection_service.py:12` | Dataclass default | `1.0` | Arbitrary |
| `full_text` fallback or pre-heading text | l.64, 77, 102 | Fixed value | `0.6` | Arbitrary, undocumented |

---

## 5. Taxonomy linking (Phase 4)

Persisted as link candidates and approved links. The confidence is **no longer
displayed** since 2026-11-18. `TaxonomyReviewPanel` shows the match type
instead ("exact preferred label", "exact alternative label", "fuzzy (similar
spelling)", "human correction"). The approved canonical label feeds the
retrieval text (section 2), so these thresholds indirectly affect
`retrieval_similarity`.

| Value | Where computed | Exact formula | Constants | Origin |
|---|---|---|---|---|
| Link `confidence_score`: exact preferred | `taxonomy/linker.py:35` `rank_with_top_uniqueness` | Normalised term equals the concept's normalised preferred label | `1.0` | Arbitrary, documented (`taxonomy-integration.md`) |
| Exact alternative label | l.39 | Equality with any normalised alternative label | `0.98` | Arbitrary, documented |
| Fuzzy | l.45 | `f = max over labels of rapidfuzz.fuzz.ratio(term, label)/100`. The candidate is dropped if `f < 0.70`. Otherwise `confidence = round(f · 0.94, 4)`. | `ratio` = normalised Indel similarity | Source (RapidFuzz) |
| | | | `fuzzy_threshold = 0.70` (l.17) | Arbitrary, documented |
| | | | Scale `0.94` | Arbitrary, documented |
| | | | Rounding to `4` d.p. | Arbitrary |
| Candidates retained | l.17 | Top `max_candidates` after sorting by `(−confidence, label, release, id)` | `5` | Arbitrary, documented |
| Auto-approval rule | `services/taxonomy_service.py:309` `link_document` | `rank == 1 ∧ unique_top ∧ confidence ≥ 0.95` | `0.95` | Arbitrary, documented (D027 calls it "the existing 0.95 threshold") |
| Human correction | `taxonomy_service.py:384` | Confidence set to a fixed value on a reviewer's concept replacement | `1.0` | Arbitrary |
| ESCO↔O*NET mapping confidence | `taxonomy/importer.py:150–157` `_mapping` | Value from the import row, default `1.0`, clamped to `[0,1]` | Default `1.0` | Source if present in the import file; otherwise arbitrary default |

Implied consequence: the fuzzy maximum is `0.94 < 0.95`, so fuzzy links can
never auto-approve. Only exact preferred and exact alternative matches can.
The `0.94` scale therefore acts as the "fuzzy is always reviewed" rule.

---

## 6. Retrieval evaluation (Phase 5 offline results)

These are produced by the CLI (`retrieval/cli.py`) and stored as evaluation
reports. They are not shown in the app UI. Results are recorded in
`docs/phase5-evaluation-protocol.md`.

| Value | Where computed | Exact formula | Constants | Origin |
|---|---|---|---|---|
| Recall@K (per candidate) | `retrieval/evaluation.py:4` `retrieval_metrics` | `|relevant ∩ ranked[:K]| / |relevant|` | `K ∈ {5, 10, 20}` | Formula: Source (standard IR). Choice of K: Arbitrary, documented (D023) |
| MRR (per candidate) | same, l.16 | `1/rank` of the first relevant job, or `0` if none | — | Source (standard IR) |
| Relevance rule | `retrieval/benchmark.py:335` `evaluate_pack` | Relevant ⇔ `relevance_grade == "2"` (scale 0/1/2) | Grade 2 only | Arbitrary, documented (D023) |
| Macro average | `benchmark.py:345` | `Σ metric over eligible candidates / aggregate_binary_query_denominator`, where the denominator is the number of candidates with at least one grade-2 job and no policy exclusion (`evaluation_policy.py:128`) | — | Methodological choice, documented (D031) |
| Exploratory grade-1-or-2 metrics | `benchmark.py` (`grade_one=True`) | The same formulas with relevance = grade ∈ {1,2}, averaged over candidates that have any relevant job | — | Arbitrary, documented (D023) |
| Corpus-size gate | `benchmark.py:316` | Rejects evaluation unless `(candidates, jobs, judgments) == (8, 30, 240)` | 8, 30, 240 | Arbitrary (study design), documented |
| Cohen's κ | `benchmark.py:431` `cohens_kappa` | `p_o` = fraction of equal grades; `p_e = Σ_g (n_left,g · n_right,g)/N²`; `κ = (p_o − p_e)/(1 − p_e)`, null if `p_e = 1` | Unweighted, 3 grades | Source (Cohen 1960) |
| Blind-export shuffle seed | `benchmark.py:17` | Seeds the pair order for the labelling CSV | `SEED = 20261002` | Arbitrary (a date) |
| Stored primary results | `phase5-evaluation-protocol.md` | Recall@5 = 0.440476, Recall@10 = 0.630952, Recall@20 = 0.714286, MRR = 0.655065 | — | **Data-derived** (outputs, not constants) |

---

## 7. Other numeric API limits (not scores)

Listed for completeness. These limit list sizes and do not change any score.
`api/routes/taxonomy.py`: search and list defaults are `20` (max `100`),
relations are `100` (max `500`), and the review queue is `25` (max `100`).
All are arbitrary.

---

## Summary of gaps relevant to Phase 6

1. **Resolved for the prototype (D036):** the 2:1 weights and 80/50 cut-offs
   were removed in favour of coverage counts. Ranking is lexicographic coverage
   until D044, retrieval similarity after it. Final
   Phase 6 scoring still needs configurable, versioned weights (MASTER_PLAN).
2. **Mostly resolved (D036):** the matcher now uses approved skills only and
   approved taxonomy concepts, with `unknown` counted as preferred. One
   difference remains: retrieval's job text includes non-rejected (pending)
   job skills, while the matcher uses approved job skills only.
3. **The extraction confidences (0.78–0.92) and section confidences (0.6/1.0)
   are fixed per-method labels.** They are not calibrated. Since D036 they are
   no longer displayed, but they are still stored and returned by the API.
4. **`retrieval_similarity` is uncalibrated** and falls in a narrow range
   (about 0.84–0.88 observed). It must stay a retrieval signal, not a
   user-facing match percentage.
5. **The taxonomy thresholds (0.70, 0.94, 0.95, 0.98) are documented but not
   derived.** They could be justified empirically against the reviewed link
   decisions already stored. No such analysis exists yet. MASTER_PLAN lists
   taxonomy-linking "confidence/calibration" as a planned evaluation topic.
6. **For reference, MASTER_PLAN's intended Phase 6 weights** are 0.35
   semantic similarity, 0.35 required coverage, 0.15 preferred coverage,
   0.10 occupation alignment, 0.05 qualification/experience alignment, plus a
   critical-skill penalty. They are planned only. None of them are in code
   yet, and they are also currently arbitrary.
