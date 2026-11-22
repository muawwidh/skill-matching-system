# Evaluation

This document describes how the system was evaluated and what was measured.
All results are descriptive: the samples are small, and none of the numbers
should be read as hiring accuracy.

## 1. Retrieval quality

### Method

- **Benchmark.** 8 candidate profiles and 30 curated English job postings.
  The profiles are de-identified and were reviewed and partly completed by
  hand, so the benchmark measures retrieval, not CV extraction.
- **Judgments.** One rater judged all 240 candidate–job pairs on three grades:
  0 not relevant, 1 partly relevant, 2 clearly relevant (167 / 54 / 19). The
  judgments were made blind to the system's rankings and frozen before scoring.
- **Primary metrics.** Recall@5, Recall@10, Recall@20 and MRR with grade 2 as
  relevant, averaged over queries (macro). One candidate has no grade-2 job;
  its recall and MRR are undefined, so 7 queries are evaluable. This exclusion
  rule was set after the judgments were collected.
- **Exploratory metrics.** The same metrics with grades 1 or 2 as relevant,
  over all 8 queries.
- **Model and representation.** `intfloat/multilingual-e5-small` at revision
  `fd1525a9fd15316a2d503bf26ab031a61d056e98`, 384 dimensions, exact cosine
  search; section-aware job text within 512 tokens.
- **Tooling.** `python -m app.retrieval.cli evaluate` computes the metrics as
  exact fractions. Benchmark inputs and judgments are private and not in the
  repository; the result files are identified by SHA-256 hashes.

### Results

Two measurements: the blind run on the frozen benchmark, and the current
system, in which every skill on the 30 jobs has been reviewed and the jobs were
re-extracted with the current job extraction (candidate profiles unchanged).

| Metric (grade 2, 7 queries) | Blind frozen run | Current system |
| --- | --- | --- |
| Recall@5 | 37/84 = 0.440 | 43/84 = 0.512 |
| Recall@10 | 53/84 = 0.631 | 25/42 = 0.595 |
| Recall@20 | 5/7 = 0.714 | 6/7 = 0.857 |
| MRR | 0.655 | 0.620 |

| Exploratory (grade 1 or 2, 8 queries) | Blind frozen run | Current system |
| --- | --- | --- |
| Recall@5 | 0.401 | 0.401 |
| Recall@10 | 0.753 | 0.716 |
| Recall@20 | 0.936 | 0.948 |
| MRR | 0.938 | 0.917 |

In the current system, four of the seven queries have a clearly relevant job
at rank 1; two queries have their only relevant job at ranks 19 and 26. With
seven queries, the differences between the two columns come from one or two
jobs moving a few places and do not show that one state is better.

Limitations: one rater (no inter-rater agreement), eight profiles, thirty
jobs, English only, profiles partly curated by hand.

## 2. Ranking variants (retrieval versus skill coverage)

`python -m app.retrieval.cli compare-matching` ranks the 30 benchmark jobs for
each candidate in four ways, read-only, and scores them with the same
judgments. nDCG@10 uses grades 0/1/2 with gain 2^grade − 1.

| Variant | Ranking | Recall@5 | Recall@10 | Recall@20 | MRR | nDCG@10 |
| --- | --- | --- | --- | --- | --- | --- |
| A | Retrieval similarity (used by the system) | 0.512 | 0.595 | 0.857 | 0.620 | 0.703 |
| B | Skill coverage, matching by name only | 0.107 | 0.310 | 0.548 | 0.151 | 0.306 |
| C | Skill coverage, ESCO concept first, then name | 0.107 | 0.310 | 0.548 | 0.150 | 0.317 |
| D | C, with retrieval similarity as tie-break | 0.107 | 0.214 | 0.643 | 0.154 | 0.382 |

For four of the eight candidates, none of their confirmed skills matched any
of the 30 jobs, so the coverage orders were decided by ties. The judgments
rate overall fit, not skill coverage, so this comparison supports using
coverage as an explanation rather than as a ranking. No significance test was
run; with seven queries none would be meaningful.

## 3. Live job import

First import (CPU-only laptop, Docker), from Arbeitnow (10 pages) and 20
Greenhouse boards, with a cap of 1,000 active jobs:

| | Arbeitnow | Greenhouse | Total |
| --- | --- | --- | --- |
| Fetched | 2,792 | 4,547 | 7,339 |
| Imported | 911 | 66 | 977 |
| Skipped: not English | ≈1,072 | ≈202 | 1,286 |
| Skipped: outside Europe and not remote | — | ≈2,344 | 2,342 |
| Skipped: duplicate posting ID / same text | | | 139 / 23 |
| Skipped: over the cap | ≈610 | ≈1,928 | 2,572 |

(≈: per-source split from a repeated, write-free fetch; totals from the run.)

- Contact details removed: 537 e-mail addresses, 162 phone numbers, 67 names.
- 7.36 extracted skills per job on average; 75.7 % of job skills got an
  automatically approved ESCO link; 20,184 link suggestions were left for
  optional review.
- Duration: about 50 s fetching, 155 s embedding all 977 jobs (0.16 s per
  job). The rest was taxonomy linking, which was then rebuilt around an
  in-memory concept index: 7.47 s → 0.099 s per job (mean) with identical link
  suggestions and automatic approvals.
- Because newer postings came mostly from Arbeitnow, each source is now limited
  to 70 % of the cap.

## 4. Response time

Synthetic candidate with 11 confirmed skills, about 980 jobs visible,
20 consecutive requests per row, CPU-only laptop.

| Request (`GET /matches/recommendations`) | Median | Max |
| --- | --- | --- |
| Page 1, 10 per page | 0.46 s | 0.60 s |
| Page 5, 10 per page | 0.46 s | 0.59 s |
| Page 1, 25 per page | 0.55 s | 0.67 s |
| Page 2, 50 per page | 0.68 s | 0.82 s |

- The exact vector search itself takes 12 ms for 978 jobs (0.55 ms inside
  PostgreSQL), so no approximate index is needed at this size.
- First request after a restart: 0.49–0.50 s once the background warm-up has
  finished (about 30 s for 1,008 jobs), 3.4–3.7 s while it is still running,
  4.5–4.7 s without warm-up.

## 5. Occupation linking for work experience

Read-only checks on the development data:

- **Experience from CVs:** only 4 of 15 CVs gave dated work entries, and none
  of their job titles linked to an ESCO occupation. Experience is therefore
  entered by the candidate.
- **Job titles linked by the automatic rule:** 230 of 977 live jobs got an
  ESCO occupation (23.5 %); 10.1 % of live jobs have both an occupation and a
  stated minimum of years, which is when related experience can be shown.
- **Group agreement of the top-3 suggestions:** +20 titles, 5 of them wrong.
  Rejected.
- **Embedding nearest neighbour:** agreed with the automatic links on all 230
  at the 3-digit ISCO level and on 156 of 230 (67.8 %) at 4 digits, but only 9
  of 20 sampled new assignments were plausible, and wrong matches had
  similarities as high as right ones. Rejected for jobs; used only to suggest
  occupations to the candidate, who chooses.
- **ISCO level:** 4 digits was too narrow and 2 digits too broad; 3 digits is used.

## 6. Isolation checks

The offline evaluation must not change when the application changes around
it. After each change that could affect it, `compare-matching` (variants A–D)
and `evaluate` were re-run on the same frozen inputs and compared
byte-for-byte with the stored outputs. All were identical:

| Checked after | Result |
| --- | --- |
| Importing 977 live jobs | identical |
| Adding related experience (work entries, experience filter) | identical |
| Storing ESCO occupation label embeddings | identical |
| Linking work entries to their source CV | identical |
| Frontend redesign with read-only dashboard endpoints | identical |
| Code clean-up and dedicated endpoints for hand-added skills | identical |

## 7. Skill extraction on live jobs

*Placeholder — to be completed.* A seeded random sample of 20 active live
jobs, labelled by hand: precision of the extracted skills and required skills
the extractor missed. Tooling: `python -m app.job_sources.cli
sample-extraction` and `score-extraction`.

| Measure | Value |
| --- | --- |
| Jobs labelled | |
| Extracted skills judged correct | |
| Required skills missed | |

## 8. Explanation quality

*Placeholder — to be completed.* A small study of whether candidates find the
job explanations (skills you have, related skills, skills to develop,
experience line) correct and useful.

| Measure | Value |
| --- | --- |
| Participants | |
| Method | |
| Results | |
