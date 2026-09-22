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

Later phases add:

1. Taxonomy linking
2. Embedding generation
3. Dense retrieval
4. Weighted scoring
5. Skill gap classification
6. Explanation generation

Each phase should introduce concrete implementations behind module-level interfaces in `app/nlp`,
`app/taxonomy`, `app/matching`, and `app/evaluation`.
