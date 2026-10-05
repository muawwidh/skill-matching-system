# Phase 5 pinned real-model verification

The machine-readable record is `phase5-real-model.json`. Verification used
only disposable, de-identified data in the isolated PostgreSQL database
`phase5_verify`; its verification schema was removed afterward. The developer
database was not queried, migrated or used for indexing. No application
runtime was deployed.

## Provenance and environment

- Model: `intfloat/multilingual-e5-small`, immutable revision
  `fd1525a9fd15316a2d503bf26ab031a61d056e98`, 384 dimensions.
- Provisioned under ignored `models/multilingual-e5-small-fd1525a`.
  The local Hugging Face metadata and generated `revision.txt` matched the
  requested revision. The evidence JSON lists every artifact filename, size
  and SHA-256 hash. Total local artifact bytes: 492,795,331; weight file
  SHA-256: `1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477`.
- Host: Apple M4, 10 CPU cores (4 performance, 6 efficiency), 16 GB RAM.
  One-shot execution container: Linux aarch64, 10 visible CPUs; Python
  3.12.15, sentence-transformers 5.1.1, transformers 4.57.6, PyTorch
  2.8.0, pgvector Python 0.4.2 and PostgreSQL extension 0.8.6. Full package
  versions are in the JSON record.
- Offline inference was demonstrated in a `--network none` container with
  `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` and a read-only model mount.
  The pinned model loaded and produced a 384-dimensional vector. An absent
  model path and an incorrect revision failed clearly. Tests did not download
  model artifacts.

## PostgreSQL verification

The representative schema began populated at `0007_taxonomy_review_audit`
and was upgraded to `0008_dense_retrieval`. It contained one approved, one
pending and one rejected candidate occurrence; four active and one archived
job; required/preferred job skills; and approved taxonomy links/canonical
labels. The actual indexing CLI indexed four jobs and one candidate profile.
An unchanged rerun was idempotent. Stale invalidation, refresh, injected
failure/retry, archived/stale/wrong-revision exclusion, deterministic ordering,
candidate API permissions, unchanged Phase 4 review records and unchanged
`CandidateJobMatch.score` passed. Repository, service and API retrieval paths
were exercised. The gated real-model test passed. The complete backend suite
afterward, with isolated PostgreSQL and offline model: **157 passed, 0 failed,
0 skipped**.

## Measured timings

These are observations on a tiny fixture, not capacity or retrieval-quality
estimates. The first load was cold to the process but may have used the host
OS file cache. Model load took 2,318 ms; candidate encode 75 ms first and
51 ms warm; job encode 12 ms first and 14 ms warm. The initial CLI job batch
processed five jobs in 0.481 s excluding process/model startup (four indexed,
one archived not ready), or 8.3 indexed jobs/s. Including startup, CLI wall
time was 4.284 s. Exact PostgreSQL cosine query mean was 1.015 ms over five
queries against four indexed active jobs; service mean was 10.202 ms and one
API request took 21.33 ms. Peak measured process RSS was approximately
866,384 KiB. The evidence JSON preserves individual query timings and
unrounded batch results.

No human-labelled job relevance set was supplied. Recall@K/MRR on real
judgments and therefore Phase 5 completion remain **PENDING**. These checks
do not establish retrieval quality or production-scale performance.
