# Matching Variant Comparison on the Phase 5 Benchmark (2026-11-18)

Read-only offline comparison (D043). The command is
`python -m app.retrieval.cli compare-matching` (`app/retrieval/matching_comparison.py`,
source commit `150574e`). It ranks all 30 benchmark jobs for each candidate
with four variants. The data is the live database after job extraction v3 and
complete job-skill review, the same state as the final Phase 5 labelled run.

Scoring uses:
- the frozen judgments, coverage policy and evaluable queries of Phase 5;
- Recall@5/10/20 and MRR (grade 2 only), with the Phase 5 definitions;
- nDCG@10 over grades 0/1/2, with gain 2^grade − 1, discount log2(rank + 1),
  and as ideal all 30 judged jobs sorted by grade.

| Variant | Ranking |
| --- | --- |
| A | Retrieval only: cosine similarity (Phase 5), ties by job ID |
| B | Skill coverage with **name matching only** (taxonomy links ignored), lexicographic, ties by job ID |
| C | Skill coverage, taxonomy concept first, then name (current rule, D036/D040), lexicographic, ties by job ID |
| D | Current app: C, with retrieval similarity as the tie-break before job ID |

## Macro averages (7 evaluable queries)

| Variant | Recall@5 | Recall@10 | Recall@20 | MRR | nDCG@10 |
| --- | --- | --- | --- | --- | --- |
| A | 43/84 = 0.512 | 25/42 = 0.595 | 6/7 = 0.857 | 0.620 | 0.704 |
| B | 3/28 = 0.107 | 13/42 = 0.310 | 23/42 = 0.548 | 0.151 | 0.306 |
| C | 3/28 = 0.107 | 13/42 = 0.310 | 23/42 = 0.548 | 0.150 | 0.317 |
| D | 3/28 = 0.107 | 3/14 = 0.214 | 9/14 = 0.643 | 0.154 | 0.382 |

## Per query

In each cell: recall@5/10/20, the rank of the first grade-2 job, and nDCG@10.

| Query | A | B | C | D |
| --- | --- | --- | --- | --- |
| Q1 | 1.00/1.00/1.00, 1, 0.925 | 0/0/0.33, 16, 0.260 | 0/0/0.33, 20, 0.260 | 0/0/0.67, 17, 0.260 |
| Q2 | 1.00/1.00/1.00, 1, 0.821 | 0/0/0, 28, 0.000 | 0/0/0, 28, 0.000 | 0/0/0, 28, 0.000 |
| Q3 | 0.25/0.50/1.00, 1, 0.694 | 0.25/0.50/1.00, 4, 0.438 | same as B | same as B |
| Q4 | 0.67/1.00/1.00, 1, 0.910 | 0.50/0.67/0.83, 2, 0.632 | same as B | same as B |
| Q5 | 0.67/0.67/1.00, 4, 0.702 | 0/0/0.67, 16, 0.277 | 0/0/0.67, 15, 0.309 | 0/0.33/1.00, 9, 0.516 |
| Q6 | 0/0/1.00, 19, 0.521 | 0/1.00/1.00, 9, 0.456 | 0/1.00/1.00, 9, 0.500 | 0/0/1.00, 11, 0.556 |
| Q7 | 0/0/0, 26, 0.352 | 0/0/0, 30, 0.078 | 0/0/0, 30, 0.078 | 0/0/0, 30, 0.269 |

Query numbers follow the sorted candidate aliases. The alias mapping stays
private.

## Reading the result

- **No significance claims.** There are seven evaluable queries and one rater.
  No significance test was run, and at this sample size none would be
  meaningful. The differences describe this benchmark only.
- **Coverage ranking is often decided by ties.** For 4 of the 8 candidates,
  namely Q2, Q5, Q6 and Q7, **no approved skill matches any of the 30
  jobs**. B and C then order those candidates' jobs only by "has
  required/preferred skills" and the job UUID, which is effectively arbitrary.
  Q6's better Recall@10 under B and C comes from this ordering, not from
  matched skills. For the other four candidates, the largest group of jobs
  with an identical coverage key has 6 or 7 jobs.
- **Concepts versus names (B → C):** the rankings are almost the same. Few
  matches depend on a taxonomy concept that the names would not also give.
- **Retrieval tie-break (C → D):** it reorders the large tie groups. nDCG@10,
  Recall@20 and MRR are higher, Recall@10 is lower.
- **A is not the reference for B to D.** The benchmark's relevance labels
  judged overall fit, not skill coverage. Coverage was designed as an
  explanation of fit, not as a relevance ranker. That the profiles are sparse
  and largely manually curated, and the CV/job vocabulary asymmetry (D042),
  are plausible contributors, not demonstrated causes.

Private outputs are in
`evaluation/local/phase5-final-and-matching-comparison-20261118/comparison/`:

| File | SHA-256 |
| --- | --- |
| `matching-comparison.json` | `80917af38f691e3d4e0e69105a6357ab860fd79e8d12039ead4d5287e61863df` |
| `rankings-A.jsonl` | `5410babf3e44f893a9fb054b6b5d96644d877addf01c7ef8ee174a9740ac1842` |
| `rankings-B.jsonl` | `82252925330a596ed8396b812fe38e1299a322447f7870ed61ed92419dbb5e9d` |
| `rankings-C.jsonl` | `43716cf1f354aca7bf99b2916d9d96890a7839b4962570ef204c22ca55fec7f5` |
| `rankings-D.jsonl` | `a471d7dd60294b48b2984821fb682778c79108624057d5f1d92a1df5b520d2b8` |
