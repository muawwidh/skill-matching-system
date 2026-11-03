# Phase 5 human-labelled retrieval evaluation pack

**Status: corpus preparation/review; human judgments and retrieval-quality metrics pending.**
Templates in `evaluation/templates/` are deliberately incomplete and fail
validation. Keep actual records under ignored `evaluation-private/` unless all
content is demonstrably permission-cleared for publication. The private
`evaluation/local/` directory is also ignored. Source PDFs and restricted
normalized descriptions must not be committed or redistributed.

## Target and schemas

Target: 8 English de-identified candidate profiles, 30 realistic jobs from
multiple occupational families and all 240 candidate-job judgments. Include
hard negatives and, where defensible, multiple relevant jobs per candidate.
Do not create relevance labels from retrieval output. Stable IDs are lowercase
ASCII letters followed by lowercase letters, digits, `_` or `-`; two to 64
characters. Never use a name, email or real account ID as an evaluation ID.

Candidate JSONL (`candidates.jsonl`), one object per line:

| Field | Requirement |
| --- | --- |
| `id` | Stable evaluation ID |
| `language` | Must be `en` for this initial benchmark |
| `profile_summary` | De-identified, author-written summary |
| `approved_skills` | Nonempty array of reviewed/approved skill strings |
| `approved_evidence_paraphrases` | Optional array of paraphrased evidence |
| `canonical_taxonomy` | Optional array of `{source, release, concept_id, preferred_label}`; use only verified identifiers |
| `source_category` | Origin class, e.g. `consented_profile` or `author_constructed` |
| `consent_or_redistribution_status` | `consented`, `redistributable`, or `author_paraphrase` |
| `deidentification_notes` | What was removed or generalized; no original identity |

Job JSONL (`jobs.jsonl`), one object per line:

| Field | Requirement |
| --- | --- |
| `id` | Stable evaluation ID |
| `language` | Must be `en` for this initial benchmark |
| `title`, `employer_label`, `region_country`, `employment_type` | Nonempty display fields; employer label must not identify a private person |
| `required_skills`, `preferred_skills` | Arrays of skills; at least one nonempty overall |
| `description_text`, `content_mode` | Canonical text and explicit `paraphrased` or `verbatim_restricted` mode |
| `description_paraphrase` | Legacy paraphrased text only; when used alone, mode defaults to `paraphrased`. Never use it for verbatim text. Conflicting dual descriptions fail. |
| `source_category` | E.g. `public_posting`, `consented_job`, `author_constructed` |
| `source_url` | Optional HTTP(S) URL; required for `public_posting` if legally appropriate |
| `access_date` | ISO `YYYY-MM-DD` date |
| `redistribution_status` | Paraphrased: `redistributable`, `author_paraphrase`, or `consented`. Restricted verbatim: only `restricted_internal_use`. |
| `redistribution_allowed` | Must be literal JSON `false` for restricted verbatim records; no inferred redistribution permission |
| `deidentification_notes` | Paraphrasing/generalization or contact-redaction record |

`verbatim_restricted` is job-only. It requires source category `public_posting`
or `consented_job`, an HTTP(S) `source_url`, non-placeholder `source_id`,
UTC `accessed_at` agreeing with `access_date`, a basename-only `pdf_filename`,
64-character lowercase hexadecimal `pdf_sha256` and `normalized_text_sha256`.
The normalized-text checksum must match the exact UTF-8 `description_text`,
including its terminal newline. Source PDF hashes establish provenance, not
copyright permission; the validator does not open PDFs or verify licensing.
Other metadata, such as uppercase display IDs, source family and classification,
may accompany records but cannot establish candidate-job relevance.

Candidate consent, de-identification and PII validation are unchanged; candidates
cannot use `restricted_internal_use`. Job text/skills still reject contact data,
including explicit recruiter-name labels. A narrowly labelled, valid
`Updated DD.MM.YYYY` job date is not a telephone number; unlabelled/invalid
dates and phone/email text still pass through the original guard. Provenance
URLs are metadata, not description text, and are permitted there.

Judgment CSV (`judgments.csv`) requires columns `candidate_id`, `job_id`,
`relevance_grade`, `reviewer_id`, `judgment_date`, `rationale`, and
`uncertainty_flag` (`true`/`false`). Extra blind-export display columns may
remain. Dates are ISO. Reviewer IDs are pseudonyms. Grade **0** means not
relevant, **1** partially relevant/plausible, **2** clearly relevant. Grade 2
alone is relevant for Recall@5/10/20 and MRR; grade 1 is retained and can be
reported in a separate exploratory grade-1-or-2 calculation. Missing judgments
are never silently treated as grade 0. Every candidate must have at least one
grade-2 job before metrics can run.

## Provenance and privacy checklist

1. Record whether each profile/job is consented, openly redistributable, or
   independently authored and paraphrased. Verify any source's terms before
   committing. A public URL is not by itself redistribution permission.
2. Remove names, contact information, exact addresses, photographs, unique
   employer/team identifiers and irrelevant protected/personal attributes.
   Automated email/phone screening is only a guardrail; perform manual review.
3. Choose the content mode honestly. Paraphrased records use independently
   written text. Locally supplied source PDFs and their faithful normalized
   text may instead be retained as `verbatim_restricted` for internal
   bachelor-project evaluation, with redistribution prohibited. Do not claim
   employer consent or a paraphrase merely because the owner supplied a PDF.
   Remove irrelevant public recruiter names, emails, telephone numbers and
   application-contact lines; retain duties, qualification distinctions,
   location and substantive employer/equal-opportunity statements. Log
   redaction categories and source page/line locations without contact values.
   Retain source URLs and original PDF hashes in provenance. Do not scrape
   restricted sites.
4. Do not export developer CV/job records. Obtain explicit consent before using
   any real person's experience, even in a de-identified paraphrase. Keep
   identity-to-evaluation mapping outside the repository.
5. Commit only content whose provenance and redistribution rights are clear;
   otherwise retain it in an ignored private directory. Publishing evaluation
   IDs, hashes, aggregate metrics and methodology does not authorize publishing
   the restricted descriptions, source PDFs or private candidate evidence.

## Labelling protocol and reviewer instructions

1. Fill and validate the candidate/job JSONL files. The tool refuses empty,
   placeholder or duplicate records. Generate pairs only after validation:

   ```sh
   cd backend
   .venv/bin/python -m app.retrieval.cli validate-benchmark ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl
   .venv/bin/python -m app.retrieval.cli blind-export ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl ../evaluation-private/blind.csv --seed 20261002
   ```

2. The blind CSV contains all pairs in reproducibly shuffled order. Save the
   printed seed/order metadata with the corpus. It contains no dense rank,
   retrieval similarity or prototype match score. Transfer the seven judgment
   fields into `judgments.csv` (or retain extra display columns). Do not look
   at any system ranking while judging. Judge fit from the approved candidate
   skills/evidence and job requirements. The profile summary is reviewer
   context, not a retrieval embedding input; it must not introduce unsupported
   or unapproved skills. Required gaps matter; a shared title alone
   is insufficient. For grade 1, explain plausible transfer and what is
   missing. For grade 2, cite concrete approved skills/evidence. Record
   uncertainty honestly and resolve ambiguous cases before finalization.
   Blind exports and their metadata are private mode-0600 files, explicitly
   marked `redistribution_allowed=false`; per-job content mode and source-use
   status accompany the text. They are not publication exports, even when a
   source is paraphrased. Restricted records are revalidated before export.

3. Validate the completed matrix. The tool rejects missing/duplicate pairs,
   unknown IDs, invalid grades/dates and candidates without grade-2 jobs:

   ```sh
   .venv/bin/python -m app.retrieval.cli validate-benchmark ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl --judgments ../evaluation-private/judgments.csv
   ```

4. Later, import only the permission-cleared benchmark into **isolated**
   `phase5_verify`, review/approve candidate occurrences, and index candidates
   and jobs with the pinned model. Keep a private mapping JSON of evaluation
   IDs to database UUIDs (see template). Export actual repository/service
   retrieval order, requiring all 30 jobs for every candidate:

   ```sh
   .venv/bin/python -m app.retrieval.cli export-rankings ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl ../evaluation-private/database-mapping.json ../evaluation-private/rankings.jsonl --database-url "$PHASE5_TEST_DATABASE_URL"
   .venv/bin/python -m app.retrieval.cli evaluate ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl ../evaluation-private/judgments.csv ../evaluation-private/rankings.jsonl
   ```

   `export-rankings` refuses database names other than `phase5_verify` and
   refuses partial job coverage. `evaluate` checks exact model/revision/template,
   corpus hashes, all candidate rankings, every judgment and the exact
   8-candidate/30-job/240-judgment target. It prints
   candidate-level and macro Recall@5/10/20 and MRR, relevant counts and
   SHA-256 checksums. It never edits raw judgments. Optional
   `--grade-one-exploratory` prints grade-1-or-2 results separately.

## Reviewer agreement

A single reviewer is the minimum but has subjectivity and no inter-rater
reliability estimate. A second reviewer can independently label the same
blind order without seeing first-reviewer grades. Reconcile disagreements in
a separate adjudicated CSV; preserve both originals. Compute optional
unweighted three-grade Cohen's kappa with:

```sh
.venv/bin/python -m app.retrieval.cli kappa ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl ../evaluation-private/reviewer-a.csv ../evaluation-private/reviewer-b.csv
```

Kappa is undefined when expected agreement is 1; the command returns `null`
then. A second reviewer is not mandatory for minimum Phase 5 acceptance.

## Completion checklist

- [ ] 8 permission-cleared, de-identified English candidate profiles.
- [ ] 30 provenance-complete English jobs in an explicit content mode with multiple families
      and hard negatives.
- [ ] Provenance and redistribution status manually checked for every record.
- [ ] All 240 pairs labelled blindly; each candidate has grade-2 jobs.
- [ ] Completed matrix passes validation; uncertainty reviewed.
- [ ] Isolated database contains only benchmark records for this run.
- [ ] Actual pinned-model rankings exported with full job coverage.
- [ ] Checksums and model provenance retained with resulting metrics.
- [ ] Limitations, single-reviewer status and any adjudication documented.

Existing safe reuse: the repository's taxonomy samples and synthetic test
fixtures are software tests, not candidate/job relevance data. They cannot
count toward this benchmark. Developer CV/job records require consent and
de-identification; this corpus-validation update did not access the application
database or export its records. The private local corpus now validates as
**8 candidates and 30 jobs**; **240 human judgments remain pending**. These
private records are not part of the committed templates, and corpus validation
is not a retrieval-quality result or final human approval of the job texts.
