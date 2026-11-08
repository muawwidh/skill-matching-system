# Phase 5 human-labelled retrieval evaluation pack

**Status: Phase 5 complete as a repository/methodology checkpoint. Frozen
Template-v2 evaluation and interpretation are accepted, including the explicit
run-specific scoped-isolation exception (D033). Latest-image deployment is
separate; Phase 6 has not started.**
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
are never silently treated as grade 0. By default every candidate must have at
least one grade-2 job before metrics can run. The only exception is an explicit,
validated local coverage policy as specified below; labels are never changed
to meet the coverage requirement.

## Explicit coverage policy (post-judgment deviation)

`evaluation/templates/evaluation-policy.template.json` defines the versioned
`phase5-evaluation-policy-v1` input. It is deliberately incomplete and invalid
until populated from an authorized methodological decision; store the completed
policy privately, not in Git. No candidate alias is hard-coded in the tooling.
An existing narrative decision is historical evidence, not automatically a
machine-valid policy. Supply the policy explicitly on **each** validation or
evaluation invocation; it is never discovered or inferred silently.

Required policy fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Exactly `phase5-evaluation-policy-v1` |
| `methodology_version`, `decision_date` | Non-placeholder methodology identifier and ISO decision date |
| `corpus_freeze_id`, `corpus_sha256` | Frozen corpus identity and lowercase hexadecimal SHA-256 |
| `input_sha256` | Exact byte hashes of `candidates`, `jobs`, and the completed CSV `judgments` export |
| `post_judgment_protocol_deviation` | Required literal boolean **true**; false, null, missing and non-boolean values fail |
| `exceptions` | Nonempty array of the candidate declarations below |

Each declaration requires `candidate_id` (blinded alias), substantive `reason`,
`grade2_coverage_status: "no_grade2_jobs"`,
`metric_treatment: {"recall_at_k": "undefined", "mrr": "undefined"}`,
`exclude_from_aggregate_binary_query_denominator: true`, and
`retain_for_graded_descriptive_analyses: true`. Flags are literal JSON booleans.
Unknown fields, duplicate JSON keys and duplicate candidate exceptions fail.
The policy file's own SHA-256 and the existing corpus/export hashes are the
authoritative provenance. Older policies containing a removed extra hash field
must be regenerated; no separate decision-file hash is accepted or reported.
Every candidate/job JSONL row and judgment CSV row must contain matching
`corpus_freeze_id` and `corpus_sha256`. The validator checks metadata consistency
and exact file hashes; it does not authenticate a decision author or recompute
the original application-data freeze payload from these files.

The candidate must exist once and genuinely have zero grade-2 judgments.
Excluding a positive-covered candidate, leaving another uncovered candidate
undeclared, an incomplete/duplicate matrix, mismatched files/freeze metadata,
or excluding every query fails. Candidate privacy, job-source restrictions and
ordinary judgment validation are unchanged. Omitting the policy remains strict.

Validation only (no vectors, rankings or metrics):

```sh
.venv/bin/python -m app.retrieval.cli validate-benchmark ../evaluation-private/candidates.jsonl ../evaluation-private/jobs.jsonl --judgments ../evaluation-private/judgments.csv --evaluation-policy ../evaluation-private/evaluation-policy.json
```

Later evaluation, **only when separately authorized**, accepts the same
`--evaluation-policy PATH` on `evaluate`. It still requires complete rankings
for all candidates and every job. The output's `query_coverage` prominently
reports total queries, evaluable grade-2 queries, excluded/undefined queries,
coverage fraction, binary aggregate denominator and excluded aliases/reasons.
Excluded per-candidate Recall@5/10/20 and MRR are JSON `null`, not zero, and
are omitted only from binary macro denominators. Policy and input hashes
accompany results. Validation and evaluation coverage limitations explicitly
state: "This coverage exception was adopted after the relevance judgments were collected."
`reviewer_limitations` explicitly reports single-rater
status and no inter-rater reliability estimate; reviewer IDs alone do not
establish independent double labelling.

The accepted private primary matrix has **8 total queries, 7 evaluable grade-2
queries, 1 excluded/undefined query, coverage 7/8 and binary denominator 7**.
Its excluded alias/reason must accompany any eventual result. This exception
was accepted after judgments: it exposes limited corpus coverage, not retrieval
performance, and is not a preregistered retrieval configuration. All 240 labels,
including grade 1, the original failed validation and historical decision remain
unchanged. There is no inter-rater reliability estimate for the single primary
rater. No metrics have been produced by this support change.

Keep uncovered candidates for separately declared graded/descriptive work.
`--grade-one-exploratory` remains separate grade-1-or-2 binary exploration, not
a graded metric or promotion of grade 1 to grade 2. It includes an excluded
primary query when it has grade-1 evidence, reports its own denominator, and
reports `null` for queries with neither grade 1 nor 2. Descriptive rows remain
present regardless. The optional `kappa` command is unchanged and does not
accept this policy; no reliability estimate is claimed here.

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

- [x] 8 permission-cleared, de-identified English candidate profiles.
- [x] 30 provenance-complete English jobs in an explicit content mode with multiple families
      and hard negatives.
- [x] Provenance and redistribution status manually checked for every record.
- [x] All 240 pairs labelled blindly; each candidate has grade-2 jobs or a valid
      explicit coverage exception, reported with undefined metrics and denominator.
- [x] Completed matrix passes validation; uncertainty reviewed.
- [x] Ranking universe isolated to the frozen corpus: original physical
      benchmark-only criterion has an explicit approved run-specific
      scoped-isolation exception (D033), not a claim of physical isolation.
- [x] Actual pinned-model rankings exported with full job coverage.
- [x] Checksums and model provenance retained with resulting metrics.
- [x] Limitations, single-reviewer status and any adjudication documented.

The owner explicitly accepted the scoped-isolation exception on 2026-11-08:
the shared-developer-database run had exactly the frozen 8 profile and 30 job
embeddings as its retrieval universe, no other entities indexed, and no
prototype-score inputs. All 29 tables remained unchanged during ranking;
13 existing legacy matches were preserved and evaluation matches remained zero.
This is not a claim that the developer database contained only benchmark rows.
Isolated PostgreSQL migration/service tests passed separately. Shared execution
was authorized before indexing; the original physical-isolation checklist
substitution is accepted explicitly at closure after evaluation. Record this
operational deviation, separately from the post-judgment coverage exception.
The general isolated workflow and CLI guard above remain unchanged for future
runs; no frozen result or source artifact is altered by this closure decision.

## Accepted Frozen Evaluation

See [the concise result report](verification/phase5-real-corpus-results.md)
for artifact hashes, exact fractions and acceptance evidence. The accepted
8-by-30 corpus has 240 judgments (167 grade 0, 54 grade 1, 19 grade 2).
Primary coverage is **7/8**, with **7** query-macro denominators and one
undefined/excluded query, `candidate_831967b28fd6`, for which no grade-2 job
was identified. Undefined is not zero. This coverage exception was adopted
after the relevance judgments were collected. A single primary rater supplied
the labels; no inter-rater reliability estimate exists.

Primary Recall@5/10/20 is **37/84 = 0.440476**, **53/84 = 0.630952** and
**5/7 = 0.714286**; MRR is **1261/1925 = 0.655065**. Optional grade-1-or-2
results remain separate with denominator 8. Two committed-evaluator runs were
byte-identical and an independent fraction implementation agreed within 1e-12.
The long-form frozen export was only grouped into the evaluator's ordered-ID
format; no retrieval, re-ranking, score change or tuning occurred in evaluation.

The profiles were manually reviewed and augmented, so this does not evaluate
end-to-end extraction. The small curated, restricted internal corpus and the
post-judgment coverage exception limit generalization; these are not production
hiring-accuracy estimates. Keep all restricted candidate/job text, private
rationales and identifier mappings outside tracked documentation.

Existing safe reuse: the repository's taxonomy samples and synthetic test
fixtures are software tests, not candidate/job relevance data. They cannot
count toward this benchmark. Developer CV/job records require consent and
de-identification; this corpus-validation update did not access the application
database or export its records. The private local corpus contains
**8 candidates and 30 jobs**; **240 primary judgments are supplied**, with the
post-judgment 7/8 coverage limitation above. The accepted frozen evaluation is
reported above; completion status is explicitly distinguished from deployment. These
private records are not part of the committed templates, and corpus validation
is not a retrieval-quality result or final human approval of the job texts.
