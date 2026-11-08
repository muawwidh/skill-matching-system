# Phase 5 Frozen Real-Corpus Retrieval Results

## Status and Scope

Independent verdict: **ACCEPT - PHASE 5 EVALUATION RESULTS**. This is an
accepted repository/methodology result. **Phase 5 is complete as a
repository/methodology checkpoint**, with the owner-approved run-specific
scoped-isolation exception (D033). This is not evidence that the latest backend
image was deployed to the normal Compose stack. Phase 6 has not started.
The corpus used an authorized, entity-scoped shared developer database rather
than a physically benchmark-only database. Isolated PostgreSQL implementation/
migration verification is separate and passed. All recorded completion gates
are satisfied under this explicit exception; no remaining implementation or
re-execution requirement is asserted.

This report contains no candidate/job text, employer descriptions, private
judgment rationales, database identifiers, credentials or alias mappings.
Detailed case interpretation remains private and Git-ignored.

## Reproducibility

- Source commit: `d80e2c921ea529561c7c6b05ade103ffa9ea7118`.
- Model: `intfloat/multilingual-e5-small`, immutable revision
  `fd1525a9fd15316a2d503bf26ab031a61d056e98`, dimension 384; local CPU inference.
- Main contract: `e5-job-profile-v2`; exact pgvector cosine retrieval.
  `e5-job-profile-v1` is a preserved baseline, not a measured comparison here.
- Corpus: `freeze_3cbd02c46bb18b60a63283a0`, SHA-256
  `61662d24b2502112aafd1d4c913c0bfd931ee58b6ba07467533f90c2f2021b3f`.
- Final labels: `final_labels_c34e61a4ff18d321440f55b3`.
- Ranking freeze: `blind_rankings_v2_9466238aa2b09e2aff28b5c7`.
- Evaluation: `evaluation_v2_4ad60a9a219015141927c755`.
- Private inputs/results are under the ignored `evaluation/local/` corpus
  directory. The public identifiers/hashes below locate immutable evidence
  without redistributing its contents.

| Artifact | SHA-256 |
| --- | --- |
| Final-label freeze JSON | `638c8fc0df9c043e83bd7ce85f5c7bbf762a4cd9af024d6c6c65638de7962e6b` |
| Completed judgment CSV | `e5739ac087ae937d3f7d038adf054c8829fb6aac2278470431b0a9f3cf358914` |
| Completed judgment JSONL | `37a5ab647a2f1485cb1cdeb87d49793bb98fdcb2faf309db0add873463126527` |
| Explicit coverage policy | `e29081e38ce5d12500afe5b4002e247eaa1c4c7659278b4b1d2e5cd4e1de92d7` |
| Frozen long-form ranking JSONL | `873521c1c14b1ce702bf3cc3070492b0dd07f305b7e1872a27082317ee5933b7` |
| Frozen long-form ranking CSV | `8f525d026a7050b144b7abf03229e736571352b84a6b079db2acac7049a3009d` |
| Ranking-freeze JSON | `9e77a86903c7bd976dbe0640d8d976172d361c3bb2168773ccc3b036e6cd686f` |
| Accepted evaluation-result JSON | `9e109b705f6cc7c52feb18755ebcf8e47d29ffa5ef435355636df94594f79970` |
| Evaluation verification JSON | `99d5877bc20cd31c9d784853c7a41eea080237eba9340ffc7760ae09ff1201f1` |
| Evaluation manifest | `a28a8413c021b5a8613d5d8f62ab18174c94a39c3bf2ecc6d54a126fc79f90da` |

## Primary Results and Limitations

**8 total queries; 7 evaluable grade-2 queries; 1 excluded/undefined;
grade-2 coverage 7/8; macro denominator 7.** The complete matrix has
240 judgments: 167 grade 0, 54 grade 1 and 19 grade 2. Only grade 2 is primary
binary relevance. Grade 0 and grade 1 are non-relevant under this definition.

`candidate_831967b28fd6` had no clearly relevant job identified by the primary
human judgments in this frozen corpus. Its primary Recall@K and MRR are
**undefined/null, not zero**. It is excluded only from binary aggregate query
denominators and retained for separately declared graded/descriptive analysis.
No grade-1 label was promoted or any judgment changed.

**This coverage exception was adopted after the relevance judgments were collected.**
It is a post-judgment corpus-coverage deviation, not a preregistered rule or a
retrieval result. Every presentation of the primary aggregates must retain the
7/8 coverage, excluded alias/reason and denominator.

| Primary Metric | Exact Macro Fraction | Decimal | Evaluable Queries |
| --- | --- | ---: | ---: |
| Recall@5 | 37/84 | 0.440476 | 7 |
| Recall@10 | 53/84 | 0.630952 | 7 |
| Recall@20 | 5/7 | 0.714286 | 7 |
| MRR | 1261/1925 | 0.655065 | 7 |

For each query, Recall@K is its grade-2 items within K divided by its total
grade-2 items. MRR is the mean reciprocal rank of the first grade-2 item.
The macro average weights the same seven evaluable queries equally; it does
not pool all 19 positive pairs into a single relevance denominator.

Limitations apply to every result in this report:

- Eight candidates and 30 curated English jobs, not a representative market sample.
- Only seven candidates evaluable for binary grade-2 metrics; one has no grade-2
  job, and the exclusion was adopted after judgments were collected.
- One primary rater; **no inter-rater reliability estimate**. Independent review
  of arithmetic/integrity is not a second relevance rater.
- Candidate profiles were human-reviewed and manually augmented. The benchmark
  does **not** measure end-to-end CV parsing or extraction quality.
- Job descriptions are restricted internal evaluation material, not redistributable.
- The real corpus used approved retrieval-universe isolation in a shared
  database, not physical database isolation. The checklist substitution was
  explicitly accepted at closure after evaluation (D033); execution itself
  had been authorized before indexing. This is separate from the grade-2
  coverage exception, and not a general change to the isolated test workflow.
- These results must not be generalized as production hiring accuracy or used
  as an automated hiring decision.

## Interpretation

Dense retrieval supplies useful candidate generation, **not a final match
score**. MRR 0.655065 indicates a clearly relevant result often appears
relatively early: four of seven evaluable queries have their first positive
at rank 1, another at rank 2, while two have first positives at 22 and 25.
This aggregate is uneven across queries, not a guarantee for every candidate.

Recall improves from 0.440476 at 5 to 0.630952 at 10 and 0.714286 at 20.
Approximately **28.6% remains outside top 20 on the macro measure**
(`1 - 5/7 = 2/7`). In raw pair counts, 10 of the 19 positives are outside
top 5, four outside top 10, and two outside top 20. The last two are the sole
positives for their respective queries; 28.6% is not the fraction of all
positive pairs missed.

Observed high-ranked grade-0/grade-1 cases show that proximity does not settle
role requirements. Broad occupational vocabulary, mixed-career or sparse
approved evidence, specialist skills, qualification alternatives and seniority
are plausible explanations, **not experimentally demonstrated causes**.
Section-aware selection is budgeted: all accepted job inputs are 503-508
tokens, but complete source wording is not retained. No miss is causally
attributed to truncation without an ablation. Candidate inputs were not
truncated. No representation, model or retrieval parameter was tuned after
the frozen rankings were seen.

Phase 6 must add explainable matching factors: reviewed skill coverage,
required/preferred distinctions, supported skill gaps, qualifications,
experience and seniority. These are recommendations, not implemented changes.
Phase 6 must not retroactively tune, replace, re-index or relabel this frozen
Phase 5 baseline; new experiments need separate versions and disclosed use of
evaluation data. A re-ranker also cannot recover a relevant job omitted by an
upstream candidate cutoff.

## Separate Exploratory Results

The existing protocol permits grades 1 **or** 2 as a separately labelled
exploration, with denominator **8**. These are not primary results, do not
replace them, and do not convert grade 1 to grade 2.

| Exploratory Metric | Exact Fraction | Decimal | Queries |
| --- | --- | ---: | ---: |
| Recall@5 | 8767/21840 | 0.401419 | 8 |
| Recall@10 | 32897/43680 | 0.753136 | 8 |
| Recall@20 | 2921/3120 | 0.936218 | 8 |
| MRR | 15/16 | 0.937500 | 8 |

## Verification and Closure Requirements

| Requirement | Evidence / Status |
| --- | --- |
| Local pinned model and provenance | `phase5-real-model.json`: immutable artifacts, offline loading and CPU inference verified |
| PostgreSQL vectors, migration and runtime | Populated 0007 upgrade/downgrade/re-upgrade to 0008, cosine retrieval, invalidation, roles and failure/retry verified in isolated PostgreSQL |
| Template v2 contract and regression tests | `phase5-template-v2.json`; v1 preserved, v2 token budgets and template isolation verified |
| Real frozen indexing | Exactly 8 profile and 30 job vectors, current v2; 38 encode calls; accepted source/artifact hashes; 27 non-embedding tables unchanged |
| Blind complete ranking | Two independent service runs; 240 alias-only rows, complete ranks 1-30, exact serialized-score equality; all 29 tables unchanged |
| Human relevance and coverage policy | Complete 240-pair matrix; explicit validated post-judgment exception; seven-query binary denominator |
| Metric reproducibility | Two committed-evaluator runs byte-identical; independent exact-fraction calculation agreed within absolute tolerance 1e-12 |
| No hidden prototype input | 13 legacy matches unchanged, zero evaluation matches; prototype scores never used for dense ranking |
| Real-corpus execution isolation | PASS under explicitly owner-approved D033 exception: shared database, only frozen 8/30 embeddings in the ranking universe, no legacy prototype inputs; no physical-isolation claim |
| Deployment | Current-source one-off runners were used. Latest-source deployment to the normal Compose stack is not claimed and is separate from methodology closure |

Evaluation used frozen files only, with a lossless long-form-to-ordered-list
projection for the committed evaluator. It did not rerun retrieval or access
the database. The accepted corpus, final-label, ranking and evaluation
manifests pass. Private result JSON/CSV retain all per-query numerators,
denominators and all 19 positive ranks without exporting restricted text.

This documentation/interpretation step does not access the application
database or perform runtime writes. It preserves the immutable evaluation
outputs and adds only documentation plus a new private interpretation report.
