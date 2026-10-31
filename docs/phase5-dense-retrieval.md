# Phase 5 dense job retrieval (implementation in progress)

This feature retrieves jobs for a candidate; it does not rank applicants,
approve taxonomy links, or calculate final matching scores. Phase 4 lexical
linking and the existing `/matches/recommendations` prototype are unchanged.

## Model and privacy

- Model: `intfloat/multilingual-e5-small` at immutable revision
  `fd1525a9fd15316a2d503bf26ab031a61d056e98` (MIT license).
- Python pins: pgvector 0.4.2, sentence-transformers 5.1.1, torch 2.8.0,
  transformers 4.57.6, huggingface-hub 0.36.2, tokenizers 0.22.2,
  numpy 2.5.3. Backend Docker uses Python 3.12 and CPU inference.
- Dimension 384; exact pgvector cosine distance; no ANN index.
- Provision explicitly from the repository root (network is used only here):

```sh
cd backend
.venv/bin/python -m app.retrieval.cli provision-model --path ../models/multilingual-e5-small-fd1525a
```

The model lives under ignored `models/`. Container runtime mounts this folder
read-only at `/models`. The local loader requires `revision.txt`, disables
remote model lookup, and fails clearly when artifacts are missing. No model is
downloaded at API startup, during requests or during tests. Use `smoke-model`
after provisioning; the pinned revision has now been executed offline in
isolated verification, as documented in `verification/phase5-real-model.md`.

CV text and embeddings can encode private experience. Only an authenticated
candidate can retrieve against their own profile; administrative/researcher
roles cannot read candidates' vectors through this API. Do not commit local
model caches, private CVs, evaluation labels or embedding dumps.

## Exact representation contract (`e5-job-profile-v1`)

All field values collapse runs of whitespace to one space. Repeated textual
values are deduplicated, then sorted case-insensitively with case-sensitive
tie-breaking. Source records are sorted by UUID before SHA-256 hashing as
canonical compact UTF-8 JSON. The source hash includes IDs, review states,
evidence, taxonomy identities/labels and the *complete* cleaned description;
it is computed before token truncation. The taxonomy fingerprint hashes the
sorted set of active linked release UUIDs whose canonical labels were used.

Candidate text starts `query: Skills: {approved reviewed skill texts and
canonical labels joined by '; '}`. A second line `Evidence: {approved evidence
snippets joined by '; '}` is present only when nonempty. Only extraction-approved
occurrences and explicitly approved manual additions contribute. An approved
taxonomy link never confirms pending/rejected extraction evidence. Canonical
preferred labels supplement matching reviewed occurrence text only while the
release is active. A profile without approved skills has no vector and returns
409 Not Ready. Complete raw CVs are never embedded.

Job text starts `passage: Job title: {title}`. Subsequent lines, when present,
are `Employment:`, `Location:`, `Required skills:`, `Preferred skills:`,
`Other skills:` and finally `Description:`. Required/preferred/unknown groups
stay distinct. Rejected job skills are excluded; pending job skills are included
because there is no equivalent candidate confirmation flow. Active canonical
labels supplement original job skill wording. Archived jobs cannot be indexed
or returned. The full cleaned description participates in the source hash.

Inputs are tokenized with the pinned model tokenizer. If they exceed 512 model
tokens including the two special tokens, retain the first 510 content tokens
in priority order and decode them without cleanup. This means long free text
may be truncated after the job title and structured skill fields. A new
representation or truncation rule requires a new template version and reindex.

## Persistence and lifecycle

Migration `0008_dense_retrieval` enables `vector` and creates
`candidate_profile_embeddings` and `job_embeddings`, each keyed uniquely by
owner, model ID, revision and template version. Owner deletion cascades.
Stored status is `ready`, `stale` or `failed`; query paths accept only `ready`
rows with current owner input hash and the exact model/template contract.
Wrong-dimension writes fail before persistence or at the vector(384) column.

Batch commands (from `backend/`, after `0008` is applied to the target DB):

```sh
.venv/bin/python -m app.retrieval.cli index jobs --limit 100
.venv/bin/python -m app.retrieval.cli index profiles --limit 100
.venv/bin/python -m app.retrieval.cli index jobs --limit 100 --after <last-job-uuid>
.venv/bin/python -m app.retrieval.cli smoke-model
```

Each command prints JSON with counts, next cursor and measured total duration.
Each item is committed independently; errors are reported and can be retried.
Reindexing an unchanged ready source is a no-op. A changed source is encoded
before the existing row is replaced; failure leaves the previous vector
stored but stale/unavailable. Job, job-skill, CV, candidate-skill and taxonomy
selection changes mark affected rows stale in their existing database
transaction. Taxonomy import/replacement marks all rows stale in the import
transaction but never runs inference there. Reindex after those changes.
Semantic job-skill corrections clear that term's active taxonomy identity and
suggestions, so an old canonical label cannot enter the next representation.
Non-semantic edits retain the selection. Every effective job-skill edit stales
the embedding; relinking/review and reindexing are explicit. Historical taxonomy
review events remain append-only, and this does not repair existing developer
records.

`GET /retrieval/jobs?limit=20` is candidate-authenticated, maximum 100. It
returns only current processed jobs, ordered by cosine distance then job UUID.
Each item contains rank, job display data, explicitly named
`retrieval_similarity`, model/revision/template, both source hashes and
index timestamps. There is no hard similarity threshold. The API performs no
inference and returns 409 when the profile is not ready/current. It never
writes `CandidateJobMatch.score` or changes `/matches/recommendations`.

## Evaluation and verification gate

For the curated, de-identified benchmark, validate the full candidate-job
judgment matrix and evaluate pinned-model rankings from isolated PostgreSQL:

```sh
.venv/bin/python -m app.retrieval.cli validate-benchmark ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl --judgments ../evaluation-private/judgments.csv
.venv/bin/python -m app.retrieval.cli evaluate ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl ../evaluation-private/judgments.csv ../evaluation-private/rankings.jsonl
```

The evaluator computes candidate-level and macro Recall@5/10/20 and MRR,
using only grade-2 judgments as relevant. It refuses unjudged pairs and
incomplete rankings; grade-1 exploration is separate. See
`phase5-evaluation-protocol.md` for schemas, blind labelling, provenance,
ranking export and the optional second-reviewer workflow. Synthetic fixtures
validate only metric calculation, not relevance quality. The pinned model and
real-model PostgreSQL retrieval have passed isolated verification; see
`verification/phase5-real-model.json` for machine-readable evidence. No
human-labelled set is available yet, so real retrieval quality remains
**PENDING**. Phase 5 is not complete until human-labelled evaluation passes.
