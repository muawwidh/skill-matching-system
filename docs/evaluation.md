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

### Method

- **Sample.** 20 jobs drawn at random (seed 20261121) from the 977 active
  live jobs, with all 145 skills the job extraction (version v3) found in
  them. Tooling: `python -m app.job_sources.cli sample-extraction` and
  `score-extraction` (with `--gaps FILE`, missed skills are read from the
  error log; jobs with no labelled row and no missed entry are excluded and
  listed, so a partly labelled sample can be scored).
  A second sample (seed 20261124, same population of 977 live jobs) is drawn
  from the final v4.1 extraction output (D061) and not yet labelled.
- **Labels.** One rater marked each extracted skill correct or incorrect and
  logged every error in a separate file with its type (missed, false
  positive, wrong mapping), category, requirement and cause. The error log is
  the single source of missed skills: a job's missed required skills are its
  logged missed items that are required and are a business skill, technical
  skill or tool. Both files are private; they are identified by SHA-256
  `b6150afa…` (labels) and `c8c68edb…` (error log).
- This is the baseline for later changes to job extraction.

### Baseline results

| Precision of extracted skills | Correct / labelled | Precision |
| --- | --- | --- |
| All skills | 111 / 145 | 0.766 (95 % Wilson interval 0.69–0.83) |
| Requirement: required | 62 / 73 | 0.849 |
| Requirement: preferred | 4 / 4 | 1.000 |
| Requirement: unknown (section not recognised) | 45 / 68 | 0.662 |
| Type: domain knowledge | 49 / 70 | 0.700 |
| Type: skill | 30 / 35 | 0.857 |
| Type: tool | 14 / 15 | 0.933 |
| Type: experience | 12 / 13 | 0.923 |
| Type: qualification | 6 / 9 | 0.667 |
| Type: certification | 0 / 3 | 0.000 |

| Missed required skills and tools (20 of 20 jobs labelled) | Value |
| --- | --- |
| Total | 163 |
| Jobs with at least one | 20 of 20 |
| Per job, mean | 8.15 |

Not counted above: 36 further missed items that are languages,
certifications, experience or qualifications, and 56 missed skills or tools
listed as preferred or as responsibilities.

**Approximate recall: 111 / (111 + 163) = 0.41.** Correct extracted items
divided by correct extracted items plus missed required skills and tools.
This is an approximation, not a true recall: the numerator counts every
correct item, including experience and qualification items and items whose
requirement is unknown, while the denominator adds only required skills and
tools that were missed. Missed preferred skills are left out, so the true
recall over all skills is likely lower. Either way, recall is the weak side of
the extractor: a job has about 7 extracted skills and about 8 missed required
skills or tools.

**Comparison: the 30 evaluation jobs.** Every skill on these jobs was approved
or rejected by hand. 289 of 357 were approved (0.810); for the 265 skills found
by version v3 rules, 207 (0.781). By requirement: required 153 / 160 (0.956),
preferred 43 / 44 (0.977), unknown 93 / 153 (0.608). These jobs were used while
the extractor was developed, and the review was done with a different aim
(keeping or removing skills, not judging the extractor), so this is an
optimistic reference, not an independent result.

### Error analysis

296 logged errors in the 20 jobs:

| Cause | Missed | False positive | Wrong mapping | Total |
| --- | --- | --- | --- | --- |
| Skill list not split into items | 141 | | | 141 |
| Term not in the vocabulary | 84 | | | 84 |
| Generic term ("IT", "certification") | | 17 | | 17 |
| No rules for languages | 15 | | | 15 |
| Text about the company, not the role | | 12 | | 12 |
| Certification asked for without a name | 10 | | | 10 |
| Recruiting boilerplate | | 5 | | 5 |
| Pattern did not match (experience) | 5 | | | 5 |
| Acronym linked to the wrong concept | | | 5 | 5 |
| Only part of the phrase extracted | | 2 | | 2 |
| **Total** | **255** | **36** | **5** | **296** |

| Missed items by category | Count | Of which required |
| --- | --- | --- |
| Business skills | 107 | 83 |
| Technical skills | 62 | 42 |
| Tools | 50 | 38 |
| **Skills and tools together** | **219** | **163** |
| Languages | 15 | 11 |
| Certifications | 11 | 2 |
| Experience | 5 | 5 |
| Qualifications | 5 | 4 |

The missed terms are spread out: 216 different terms, 189 of them seen only
once. The most frequent are "English" and "artificial intelligence (AI)" (6
jobs each), then "go-to-market (GTM)", "enterprise sales", "APIs" and
"presentation skills" (3 jobs each); 21 further terms appear in 2 jobs, among
them German, French, GCP, TOGAF and Microsoft Excel.

Most misses (141 of 255) are skills written as a comma-separated list that the
extractor reads as one unit; most of the rest (84) are terms that are not in
the vocabulary at all. False positives come mainly from generic words and from
text describing the company rather than the job.

Limitations: one rater, 20 jobs, English only; the causes were assigned by the
same rater.

### Design iteration: v3 → v4 → v4.1

The error analysis suggested splitting skill lists (most misses) and filtering
generic and company text (most false positives). Three rule versions were run
on the same 977 live jobs (2026-11-24). Counts are over active live jobs;
"required items" are required skills, tools and domain knowledge, one per
distinct name per job; "linked" is the share of them with an approved ESCO
link. Item quality of v4 and v4.1 comes from unlabelled random checks of list
items by the developer (jobs outside both samples), not from the labelled
sample, and is indicative only.

| Version | Items per job | List items per job | Required items per job (mean / median) | Jobs with no required item | Linked share | Item quality |
| --- | --- | --- | --- | --- | --- | --- |
| v3 (baseline) | 7.36 | — | 2.0 / 1 | 446 | 82.7% | precision 0.766 on the labelled sample (all items) |
| v4: lists split, guards | 18.91 | 11.94 | 11.9 / 8 | 382 | 15.1% | 3 of 10 random list items useful |
| v4.1 first pass: list item must be in the vocabulary | 7.34 | 0.36 | 2.2 / 1 | 462 | 74.6% | 14 of 20 useful, 1 unclear, 5 noise |
| v4.1 final: no one-word non-digital ESCO labels, no languages | 7.13 | 0.16 | 2.0 / 1 | 479 | 76.4% | 20 of 20 useful (19 tool names) |

- **v4** splits lists in requirement sections and adds language,
  certification and guard rules. It multiplied the items, but most list items
  were fragments or generic phrases ("business masterminds", "Deep",
  "Deutschlandticket").
- **v4.1** keeps a list item only if it is a curated dictionary entry, an
  ESCO skill/knowledge label or an O*NET Technology Skills tool name. Most
  known terms were already found by the dictionary and ESCO scan, so only 354
  of 11,662 v4 list items stayed. The final clean-up also drops one-word ESCO
  labels outside the digital collection ("measurement", "curiosity",
  "design") and language names, leaving 152 list items, 142 of them tools.
  Tool names from O*NET have no ESCO link, which lowers the linked share
  slightly.
- **Outcome.** v4.1 keeps v4's language and certification rules and guards
  but gives up most of v4's recall gain: it recovers mainly tool names
  written in lists. Precision was preferred over recall (D061). The recall of
  the final version is measured on the second sample once it is labelled.

## 8. Explanation quality

*Placeholder — to be completed.* A small study of whether candidates find the
job explanations (skills you have, related skills, skills to develop,
experience line) correct and useful.

| Measure | Value |
| --- | --- |
| Participants | |
| Method | |
| Results | |
