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
