# Processing Flow

Phase 2 implements the first concrete processing pipeline steps:

1. Document ingestion
2. Text extraction
3. Text cleaning
4. Section detection
5. Skill/tool/qualification/occupation extraction
6. Evidence sentence capture
7. Candidate skill review
8. Result storage
9. Processing logs

Readable PDF text is normalized during upload/parsing, before cleaning and
section detection. A genuine line-boundary heading or line-start `Heading: body`
delimiter is recognized by section detection. PDF normalization additionally
splits a flattened line only when it begins with a known all-uppercase heading
and has either two more such headings or a second one after sentence-ending
punctuation. One longest-first,
non-overlapping pass keeps multiword headings intact; uncertain inline words
remain prose. `Education and certifications` on its own line is one education
heading. Non-whitespace text before the first heading is retained as `full_text`;
named section spans exclude heading text but retain exact body offsets.

The extractor contract is `v2`, defined by `EXTRACTION_CONTRACT_VERSION` in
`backend/app/nlp/skill_extractor.py`. New candidate and job extracted terms
persist it in their existing `extraction_method` field as `dictionary@v2`,
`regex@v2`, or `spacy_phrase_matcher@v2`. The default Docker path uses the
dictionary regex implementation; optional spaCy output is separately identified
and is not claimed to be identical. Bump the constant whenever extraction
behavior changes. No package-version or environment-specific value enters it.

Every extraction created before Stability Batch 4 has a legacy
`extraction_method` value. That field participates in Batch 2's complete
occurrence reconciliation key, so deliberately reprocessing a pre-v2 CV
replaces all its legacy extraction occurrences even when visible text and
offsets are unchanged. Its approved, rejected and pending extraction reviews
become newly extracted `pending` skills; a formerly rejected skill may
temporarily enter the transitional prototype matcher, which excludes rejected
but includes pending skills. Taxonomy candidates and selected links for the
replaced terms are removed, while taxonomy review audit events stay append-only.
The existing invalidation lifecycle marks the candidate embedding stale.
Review and relink all reprocessed pre-v2 evidence before indexing or benchmark
evaluation. This contract-version boundary does not migrate reviews safely.
There is no requirement to reprocess reviewed legacy CVs immediately; leave
them untouched unless deliberately regenerating and re-reviewing their evidence.

Ordinary `process_cv` uses the CV's already-stored raw text; it does not rerun
PDF parsing or normalization. Reprocessing does not repair legacy PDF
normalization. Affected PDFs must be uploaded again to receive the corrected
stored text; that creates a new CV lifecycle and does not inherit prior reviews
automatically. Evaluation CVs must be uploaded only after
this batch is accepted. Extraction-derived evidence from affected inputs must
be regenerated before benchmark evaluation. Phase 4 package-import evidence
and Phase 5 real-model artifact evidence remain valid.

Phase 4 added lexical taxonomy linking and review. Phase 5 adds a separate
retrieval branch after review:

1. Build an approved-evidence candidate profile and processed-job texts
2. Explicitly index both with the locally pinned E5 model
3. Retrieve top-N active jobs by exact pgvector cosine distance

Later phases add:

1. Final weighted scoring
2. Skill gap classification
3. Explanation generation

Each phase should introduce concrete implementations behind module-level interfaces in `app/nlp`,
`app/taxonomy`, `app/matching`, and `app/evaluation`.
