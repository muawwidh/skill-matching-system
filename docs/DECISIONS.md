# Architecture and Methodology Decisions

## D001 — Layered Architecture

Use:

Frontend
→ API Routes
→ Services
→ Repositories
→ Database/domain modules

Reason:

Maintain separation of concerns and testability.

## D002 — PostgreSQL

PostgreSQL is the main persistent database.

Reason:

Relational integrity and future pgvector integration.

## D003 — Alembic

All schema evolution uses Alembic migrations.

Do not modify previously applied migrations to introduce new schema changes.

## D004 — Local ESCO/O*NET Storage

ESCO and O*NET releases are imported and stored locally.

The matching system must not depend on live taxonomy APIs for every match.

Reason:

- reproducibility
- performance
- availability
- version control
- thesis evaluation consistency

## D005 — Sample Taxonomies

Bundled ESCO/O*NET samples exist only for development/testing.

They must remain clearly identified as sample releases.

## D006 — Taxonomy Confidence

High-confidence deterministic taxonomy links may be automatically approved.

Uncertain mappings remain reviewable.

Multiple ranked candidates may be stored.

Reason:

Incorrect taxonomy normalization can negatively affect downstream
matching and gap analysis.

## D007 — Extraction Evidence

Repeated term occurrences may remain separately stored when each represents
different evidence.

Candidate-facing normalized skills should be deduplicated separately.

## D008 — PDF Baseline

Readable PDF text extraction is supported.

PDF text normalization is used before section detection where appropriate.

OCR is not currently a baseline requirement.

## D009 — Dense Retrieval Is Not Final Scoring

Vector similarity in Phase 5 is used only to retrieve top-N relevant jobs.

It is not the final match score.

## D010 — Early Matching Is Transitional

The matching implementation created after Phase 3 is a prototype for later
Phase 6 development.

It should be expanded/refactored rather than treated as the completed
matching methodology.

## D011 — Versioned Final Scoring

Phase 6 scoring configuration must be configurable/versioned.

Reason:

Reproducibility and evaluation.

## D012 — Explanation Grounding

Match and skill-gap explanations must derive from stored structured evidence.

Unsupported explanation text is not acceptable.

## D013 — Data Minimization

Matching excludes irrelevant personal attributes such as:

- age
- gender
- religion
- nationality
- marital status
- photographs

## D014 — Administrative Separation

System-wide logs, taxonomy management and similar administrative data are
restricted to administrator/researcher users.

## D015 — Development Taxonomy Docker Mount

Repository ./data is mounted as /data inside the backend development
container.

Reason:

Phase 4 sample taxonomy loading resolves data from /data/sample.

## D016 - Pinned Native Package Contracts

Native package support is pinned to ESCO 1.2.1 classification English CSV and
O*NET 29.0 tab-delimited TXT and O*NET 31.0 CSV. Exact files/headers and optional dependencies are
explicit contracts, not heuristic column aliases. Other versions/formats require
their own implementation and verification. Legacy flattened formats remain
separate development/interchange paths. Full-package PostgreSQL evidence is
required in addition to fixtures before claiming official-format support.

## D017 - Lossless Structured Taxonomy Data

ESCO relationships have directed, same-release endpoints enforced by composite
foreign keys. Original relationship rows preserve essential/optional and skill
type semantics. O*NET rows retain typed identifiers and exact numeric values plus
complete source fields and release-scoped scale/category reference records.
Source metadata is retained for reproducibility, not used as an unsupported score.

ESCO v1.2.1 repeats some concept URIs with only modifiedDate differences. Merge
these into one concept while retaining every source row and reporting merged
counts. Conflicting semantic fields fail rather than choosing a row silently.

## D018 - Atomic Release Replacement

Validate before writing; serialize same-source PostgreSQL imports with a transaction
advisory lock. Replacement and activation commit as one transaction. Any failure,
including after deletion or partial inserts, restores the previous release and its
dependent mappings/reviews. Successful same-version replacement retains the prior
documented lifecycle: dependencies may cascade away, requiring mapping reimport
and extracted-term relinking. No automatic review-decision migration is implied.

## D019 - Explicit Taxonomy Selection and Review Audit

The approved link is the authoritative selection for a term_source/extracted_term_id
pair. A replaced approval becomes `superseded`: previously selected, not semantically
incorrect. Only explicit rejection marks a suggestion incorrect. Rejecting the
selected candidate removes its approved link; rejecting alternatives preserves it.

Selection replacement requires explicit confirmation against the current selection
token. PostgreSQL transaction advisory locks serialize term reviews and relinking.
Selection, status reconciliation and before/after audit snapshots commit atomically.
Repeated identical reviews are no-ops, preserving original timestamps and history.

Audit snapshots retain concept labels/identifiers and previous reviewer information.
They intentionally have no candidate/term foreign keys, so reprocessing or release
replacement does not erase recorded history. Reviewer deletion sets the actor FK to
null. This preserves history, not live links: D018 replacement semantics are unchanged.
No historical events are fabricated and migration 0007 does not repair legacy rows.
Legacy inconsistency is exposed for an explicit subsequent review through the UI.

## D020 - Candidate Skill Presentation Groups

Candidate-facing consolidation is a read projection, not evidence deduplication.
Approved taxonomy links group by concept UUID plus taxonomy release UUID. Source,
version and preferred label are shown; neither equal labels nor cross-taxonomy
mappings imply identity. Unlinked occurrences group by the exact pair of skill_type
and lowercase stored normalized_text, reusing extraction/save normalization without
additional punctuation stripping, fuzzy comparison or alias inference. Linked and
unlinked occurrences are never forced into one group.

Every occurrence keeps its ID, evidence, confidence and extraction review decision.
Only extraction-approved occurrences provide confirmed support in this presentation;
pending/rejected evidence is not confirmed by a taxonomy mapping. This does not
redefine matching scores. Individual corrections invalidate that occurrence's mapping
and suggestions, update its term for later relinking, and preserve evidence/history.
Status-only extraction review does not change taxonomy review. Legacy text/term
mismatches are presented without taxonomy identity until corrected/relinked.

## D021 - Separate O*NET Release Adapters

Dispatch 29.0 TXT and 31.0 CSV to separate version-pinned adapters sharing only
archive safety and transactional persistence. The 31.0 manifest declares every
supported dataset and its identity columns. Do not retrofit CSV naming/semantics
onto the verified TXT adapter or imply unsupported release compatibility.

Preserve every CSV row, including multi-endpoint relationships, in structured
source_data. Materialize content-reference nodes and explicitly directed binary
links using the rules in onet-31-contract.md; do not flatten triple/task records
into interchangeable labels. Source rows remain authoritative for richer semantics.
This extends coverage without changing the release replacement lifecycle or scoring.

## D022 - Phase 5 Job Retrieval Is Separate From Taxonomy Linking And Scoring

Phase 5 indexes only approved candidate evidence and processed job text with
an immutable local multilingual E5 revision. Pending/rejected extraction
occurrences do not confirm candidate skills; pending job terms may be indexed
until job review catches up. Canonical taxonomy labels supplement, but never
replace, reviewed wording. Full normalized inputs are hashed before token
truncation, and status invalidation prevents stale vectors from retrieval.

The vector store uses revision/template-keyed rows and exact pgvector cosine
distance. Top-N similarity is exposed only as retrieval similarity, never
written to CandidateJobMatch.score. Phase 4 lexical linking and review history
remain authoritative and are not regenerated by indexing. Semantic taxonomy
suggestions, approximate vector indexes and Phase 6 scoring are out of scope.

## D023 - Complete Blind Human Retrieval Benchmark

Phase 5 retrieval quality uses a curated, de-identified candidate-job matrix,
not synthetic arithmetic fixtures or inferred relevance labels. Every candidate
must be judged against every benchmark job in a blinded, reproducibly shuffled
presentation. Grade 2 alone defines binary relevance for Recall@5/10/20 and
MRR; grade 1 remains available for explicitly separate exploratory analysis.
Unjudged pairs are never assumed irrelevant. A single reviewer is acceptable
for minimum acceptance, with the subjectivity limitation documented; a second
reviewer and unweighted three-grade Cohen's kappa are optional. Only records
with appropriate consent, de-identification and redistribution status may be
committed; otherwise the real corpus stays in an ignored local directory.

## D024 - Retained CVs Contribute To One Candidate Profile

A candidate profile accumulates eligible evidence from all retained CVs, while
extraction review and taxonomy selection remain occurrence- and CV-scoped.
Processing or deleting one CV must not change another CV's skills or reviews.
Manual profile skills are independent of CV deletion.

Same-CV reprocessing preserves a uniquely identical extracted occurrence and
its review identity. If complete occurrence fields change or duplicate keys
are ambiguous, only that CV's superseded derived rows are replaced. This is
not a general repeated-evidence matching policy. CV deletion removes derived
skills before their SET NULL term FK can orphan them; append-only taxonomy
review events are retained pending a separate privacy-retention decision.

## D025 - Database Migrations Are Explicit Operator Actions

Serving application traffic must not apply Alembic migrations. Backend container
startup reads the repository and database revision head sets and starts only when
they match exactly; an absent, divergent or unreachable database fails closed.
The checker is read-only and reports no database credentials. The same backend
image exposes an opt-in Compose maintenance service for explicit
`alembic upgrade head`; ordinary Compose startup neither runs nor depends on it. Backups and
upgrade timing remain operator responsibilities.

## D026 - Conservative PDF Headings And Versioned Extraction Provenance

PDF normalization must not infer headings from ordinary inline prose. Section
headings need line-boundary or explicit delimiter evidence; recovery from a
flattened PDF line requires a known uppercase heading at its start and either
two more uppercase headings or a second after sentence-ending punctuation.
Longest-first non-overlapping recognition
keeps multiword headings together. Uncertain text remains prose, and meaningful
preamble text remains extractable as `full_text`.

Extractor behavior is identified by a stable `v2` contract in the existing
extracted-term `extraction_method` field. Dictionary-regex, regex-indicator and
optional spaCy methods remain distinct; a later behavior change must bump the
contract constant. This is provenance for newly persisted terms, not a
retroactive classification of old terms or a correction-history mechanism.

## D027 - Equal-Confidence Distinct Taxonomy Concepts Need Human Review

Automatic taxonomy approval requires a unique highest-confidence concept above
the existing 0.95 threshold. Matching labels on the same release-scoped concept
are deduplicated before this decision, keeping its strongest match method and
confidence. Distinct concepts tied at the top remain pending even if a stable
label/release/UUID sort gives one of them rank 1 for display. That ordering is
not evidence that one concept is semantically superior. Existing selected links
and append-only review events are not rewritten by this rule; any historical
cleanup requires a separate authorized inventory and decision.

## D028 - Semantic Job-Skill Corrections Invalidate Taxonomy Selection

Changing a job skill's raw text, normalized text or skill type changes its
taxonomy identity. The associated extracted term is updated and its active
selection and suggestions are removed in the same transaction. This is
invalidation, not a human rejection or a replacement approval; append-only
review events remain historical. Evidence, requirement and extraction-review
edits preserve the taxonomy selection. Any effective job-skill edit stales
the job embedding transactionally; reindexing and any relinking/review are
explicit. Existing developer records are not retroactively repaired.

## D029 - Private Verbatim Evaluation Sources Are Not Paraphrases

Locally supplied original job PDFs and contact-redacted normalized text may be
private bachelor-project evaluation material, explicitly `verbatim_restricted`
with `restricted_internal_use`, complete source/hash provenance and
`redistribution_allowed=false`. They must never be labelled as paraphrased or
redistributable. Recruiter names and application contact details are not
matching evidence. Candidate privacy and consent rules remain independent.
Legacy legitimate paraphrased job records remain supported. Blind labelling
exports are private and retain content-mode/use restrictions; publication may
include evaluation IDs, hashes, metrics and methodology, not restricted
descriptions, source PDFs or private candidate evidence. Source hashes and an
owner-supplied PDF do not assert employer consent or a redistribution licence.

## D030 - Predeclared Section-Aware Retrieval Template V2

`e5-job-profile-v1` remains an explicitly selectable, unchanged baseline, with
its historical verification evidence retained. `e5-job-profile-v2` is the default
and main evaluation contract. This policy was defined before human relevance
judgments or retrieval rankings were viewed; coverage debugging is not relevance
evaluation. No job IDs, candidate families, occupational dictionaries or
per-record exceptions select source text. Candidate v2 text is identical to v1;
its source hash separately identifies the v2 contract.

Recognized headings supply the source class by default. `Desired Skills` and
`Desired Qualifications` are preferred headings. A preference cue overrides a
heading only when the whole original line is clearly optional: a leading
preferred marker or a whole-line preferred predicate, without mandatory or
mixed-clause evidence. Parenthetical/bracketed or subordinate preferences do
not make an otherwise required line optional. Mixed lines retain their explicit
heading class and wording; no semantic fragments are invented. This correction
was fixed while v2 was unreleased, before it was committed, indexed or used for
relevance labels. J12's former weak preferred coverage was a classification
defect, not token-budget truncation.

Job v2 prioritizes metadata, non-rejected structured skills/canonical labels,
then verbatim source sections. Fixed metadata/structured caps are 104/96 tokens;
remaining capacity is reserved across requirements, preferences,
responsibilities, summary and context with weights 4:2:4:1:1. Empty classes
redistribute capacity; unused quotas are refunded without sacrificing already
reserved classes. Generic heading grammar and linguistic cues refine stored
sections without modifying extraction. Source-order snippets are stratified
before filling unused space. The exact pinned offline tokenizer, including
special tokens, enforces the 512-token ceiling. Full source inputs, final text,
template and model revision are hashed. This is selection, not paraphrasing,
newly confirmed skills or complete preservation of every source condition.

Both templates remain separate persistence/query identities. Switching requires
explicit indexing of both profiles and jobs under the same template; it does
not migrate reviews or overwrite baseline vectors. Recall@K/MRR may later
compare v1 and v2 as separate predeclared configurations. No retrieval-quality
claim follows from coverage or synthetic tests alone; accepted real-corpus
evidence is recorded separately in `verification/phase5-real-corpus-results.md`.

## D031 - Explicit Zero-Grade-2 Corpus-Coverage Exceptions

The default benchmark requirement remains at least one grade-2 job per
candidate. An operator may supply a versioned, local evaluation policy to
`validate-benchmark` and `evaluate` to declare a genuine uncovered query.
It must identify the frozen corpus, exact candidate/job/judgment file hashes,
candidate alias, reason, decision date and methodology version. Every bound
record must carry the same freeze ID/hash. Unknown/duplicate aliases,
positive-covered exclusions and undeclared uncovered queries are errors;
exclusions are never inferred from labels or retrieval output.
Policy v1 requires literal `post_judgment_protocol_deviation=true`; false,
null, missing and non-boolean declarations fail. Validation and evaluation
limitations state: "This coverage exception was adopted after the relevance judgments were collected."
The policy file's own hash and existing corpus/export hashes establish the
provenance binding; no separate source-decision hash is accepted or reported.

An explicitly excluded query has undefined (`null`), not zero, binary Recall@K
and MRR. Aggregate binary metrics use only positive-covered queries and must
report total/evaluable/excluded counts, coverage, denominator and each excluded
alias/reason. All judgments remain immutable, including grade 1; the query
remains available for separately declared graded/descriptive analysis. Optional
grade-1-or-2 analysis has its own explicitly reported denominator. Full-matrix
and full-ranking coverage requirements still include excluded queries.

The project owner's accepted private case is a **post-judgment corpus-coverage
deviation**, not a preregistered policy or a retrieval result: 7/8 queries have
grade-2 coverage, one has none, and future binary aggregates have denominator
7. The original failed validation and completed exports are retained. No
judgment is promoted or re-reviewed to manufacture coverage. Report this
limitation prominently, together with single-rater subjectivity and absence of
an inter-rater reliability estimate. At this policy checkpoint Phase 5 remained
incomplete; this decision alone did not authorize indexing, rankings or metrics.
Later explicitly authorized execution is documented in the frozen result report.

## D032 - Frozen Phase 5 Evidence Is Not Retuned By Phase 6

The accepted Template-v2 real-corpus evaluation is an immutable candidate-
generation baseline, not a final job-match score. Keep its model/revision,
templates, labels, coverage policy and complete frozen ranking unchanged after
interpretation. No observed success or failure retroactively authorizes a new
embedding, label, threshold or representation under the same baseline identity.
Later scoring/retrieval experiments require separate versions and disclosure
of their evaluation-data use; they must not replace the historical baseline.

Phase 6 may add the planned explainable reviewed-skill coverage,
required/preferred distinctions, gaps, qualifications, experience and seniority.
Those factors must derive from supported evidence, not similarity alone, and
must not infer mastery, completed qualifications or independent practice from
limited/reported/supervised evidence. Preserve missing versus unknown support.
No Phase 6 implementation is introduced by this decision.

## D033 - Run-Specific Scoped-Isolation Exception For Phase 5 Closure

The owner explicitly accepted the authorized shared-database corpus run as a
scoped-isolation exception for Phase 5 repository/methodology closure on
2026-11-08. The original benchmark-only physical-database criterion is not
silently described as satisfied: this run used the existing developer database.
Only the frozen 8 profile and 30 job embeddings formed the retrieval universe;
other profiles/jobs had no vectors. The 13 existing prototype matches were
excluded from dense ranking and preserved, with zero evaluation matches.
All 27 non-embedding tables remained unchanged during indexing, as demonstrated
by the recorded before/after database-table fingerprints.
Read-only ranking preserved all 29 table fingerprints, including all vectors.

The scoped-isolation evidence comprised a pre-indexing PostgreSQL custom-format
backup stored outside the repository and successfully checked with
`pg_restore --list`; before/after database-table fingerprints; private alias
mappings binding frozen aliases to the intended database entities; and SHA-256
manifests for the corpus, indexing, ranking and evaluation artifacts.

Shared execution was authorized before indexing. Its acceptance as a substitute
for the earlier checklist criterion is explicit at closure, after evaluation,
not a preregistered physical-isolation claim. This is an operational isolation
deviation, separate from the post-judgment zero-grade-2 coverage deviation
(D031); neither changes the labels, ranking, metric denominator or result.
Independent isolated PostgreSQL migration/service/model verification remains
separate evidence. The generic isolated-only ranking-export CLI guard and the
default isolated verification workflow are unchanged. Future reproductions
should preferably use a dedicated isolated benchmark database. This authorized
exception is not precedent or general permission to use a shared developer
database for future experiments.

Phase 5 is complete as a repository/methodology checkpoint with the recorded
limitations. Current-source one-off execution does not claim the latest normal
Compose image is deployed. Phase 6 has not started, and must preserve the frozen
Phase 5 baseline under D032.

## D036 - Transitional Matching Reports Skill Coverage, Not A Score

(Numbered D036 to avoid colliding with D034/D035 on branch
`phase6-explainable-matching`; D034 and D035 are intentionally absent here.)

The transitional matcher on the Jobs page no longer produces a match
percentage. Its former 2:1 required/preferred weights and 80/50 explanation
cut-offs were arbitrary and undocumented (`docs/score-inventory.md`). It now
reports coverage counts: "Required skills: X of Y matched" and
"Preferred skills: X of Y", plus the matched and missing skill labels.

Only approved skills are compared, on both the candidate and the job side.
Pending and rejected extraction reviews are never treated as evidence. Two
skills match by taxonomy concept ID when both carry an approved,
text-consistent link on an active release. Otherwise they match by identical
normalized text. Each matched skill records which of these applied. When both
are linked to different concepts, the reviewed links take precedence and no
name fallback applies. A linked job skill with no matching candidate skill is
missing. An unlinked job skill with no same-name candidate skill was at first
excluded as "could not be compared"; D040 replaced this, and it now counts as
missing. Job requirement type `unknown` counts as preferred,
not required. When one skill is listed as both, required wins.

Only skill-like types (skill, tool, domain knowledge, language) are compared.
Approved qualification, experience, certification and occupation terms are
listed as "not assessed by the system" and never scored. The Phase 6 plan
treats qualification/experience alignment as a separate component.

(Ranking superseded by D044: the app now orders by retrieval similarity.)
Jobs are ranked lexicographically rather than by weighted combination. The
keys, in order, are:
1. Required coverage. Jobs with no comparable required skills go last.
2. Preferred coverage. Within equal required coverage, jobs without
   comparable preferred skills sort after those with some.
3. Phase 5 retrieval similarity, when both the profile and the job index are
   fresh. Unavailable similarity sorts after available similarity.
4. Job ID.

D040 inserts the matched counts between keys 2 and 3.

Coverage is compared as an exact fraction, so 1 of 1 and 2 of 2 have equal
coverage.
Similarity is only read for ordering. It is never displayed, and Phase 5
indexes, templates and evaluation are unchanged (D032). Explanations are
built only from the stored matched, missing and not-assessed lists. Recommendations are recomputed on every read, so stored rows cannot
reflect an older rule or stale reviews. The legacy `score` column is kept
without a migration and stores required coverage × 100. It is not displayed
or used for ranking.

Concept IDs are release-scoped. An ESCO and an O*NET concept for the same
skill do not match. The existing ESCO↔O*NET mapping table is a possible
future bridge, but it is not used. This remains a transitional prototype, not
the final Phase 6 scoring, which must still be configurable and versioned.

## D037 - Job Rankings Are Visible Only To Their Owner

A candidate's job ranking and skill coverage are shown only to that candidate,
on the Jobs page ("#N of M"). Administrators and researchers get no
per-candidate ranking view or endpoint. Their dashboard overview contains
aggregate counts only (purpose limitation and data minimisation). The system
is career decision support for the candidate. A view ranking candidates for
an employer or reviewer would turn it into a screening tool, which is outside
its purpose.

Dense retrieval stays an internal ranking signal. (Since D045 it selects and
orders the top-N jobs; originally it was the tie-breaker under D036.) It is
evaluated offline. It has no candidate-facing page and no
displayed similarity. The only cross-candidate ranking access is the offline
Phase 5 evaluation export, which is restricted to the isolated
`phase5_verify` database and its de-identified benchmark accounts (D023).

## D038 - Job Extraction Contract v3: Heading Requirements, Experience Ranges, ESCO Vocabulary

Job extraction moves to contract `v3`. CV extraction stays on `v2`. Three
changes:

(a) **Requirement type from section headings.** A job-only segmentation
(`detect_job_segments`) reuses the predeclared heading table of the frozen
retrieval v2 template (`job_budget.HEADINGS`) plus "must have", "bonus" and
"qualifications". Requirements and Qualifications sections give `required`.
Preferred, Desirable, Nice to have and Bonus give `preferred`. Responsibilities,
summary, company context and untitled text give `unknown`. Text under
Benefits, Equal Opportunity / EEO, How to apply, application or screening
questions, Compensation, Salary and Why join us is not extracted. Since
2026-11-18 company values and culture headings are also excluded ("Values",
"Our/Core/Company Values", "Our Culture", "Values and Behaviours", "Attributes
aligned with Core Values"). They describe the employer, not the role. When the
list was extended, no stored term on any active job came from such a section.
Excluded headings count only when they stand alone on their line. The shared
`SectionDetectionService.detect` is unchanged. CV sections and stored job
sections (display and retrieval input) are not affected.

(b) **ESCO labels as a second dictionary, filter O7.** This uses the preferred
and alternative labels of skill/knowledge concepts in the active, non-sample
ESCO release (here 1.2.1; 96,108 usable labels after filtering). A label is
used if its concept is in the ESCO Digital collection (concept scheme
`6c930acd-…`, 1,284 concepts, identical to `digitalSkillsCollection_en.csv`),
or if the label has at least two words and the concept is not transversal.
Single-word labels need at least two characters. When ESCO capitalises one
(e.g. "Python", "LESS"), it must appear with that spelling. The longest
non-overlapping match wins within a line. Curated dictionary matches win any
overlap. ESCO terms are stored with method `esco_vocabulary@v3:ESCO-<release>:o7`
and fixed confidence 0.8, an uncalibrated label like the other per-method
values. They are linked to taxonomy concepts by the normal linker. Config
`JOB_EXTRACTION_ESCO_VOCABULARY` (default on) switches the vocabulary off for
old-vs-new comparison.

(c) **Experience ranges.** The job experience pattern accepts "3-5", "1 to 3"
and "0–2" ranges, "3+ years", and up to three words before "experience".

**Justification (stage-1 diagnosis on the 30 Phase 5 evaluation jobs,
2026-11-18, in memory, no DB writes):**

| Measure | v2 | v3 |
|---|---|---|
| Terms by requirement (a) | 9 required / 8 preferred / 75 unknown of 92 | 54 / 13 / 29 of 96 |
| Experience matches (c) | 5 in 5 jobs | 20 in 16 jobs |

- For (a), 11 jobs have no heading the v2 detector recognises, 51 terms change
  type and 2 terms under benefits, EEO or how-to-apply text are dropped.
- For iCapital "Data Feed Operations – Associate", (a) changes the result from
  0 of 7 terms required to 4 of 7.

ESCO filter options compared (b), as distinct concepts over the 30 jobs:

| Option | Concepts |
|---|---|
| all labels | 436 |
| multi-word only | 142 |
| Digital collection only | 151 |
| non-transversal | 365 |
| multi-word and non-transversal | 125 |
| Digital, or multi-word and non-transversal | 224 |
| O7 (previous, plus the casing guard) | 200 |

The rejected options fail for these reasons:
- **All labels and non-transversal:** they admit generic words ("communication"
  in 25 jobs, "it", "re", "plan", "lead", "integrity").
- **Multi-word only:** loses Python, SQL and PostgreSQL.
- **Digital collection only:** keeps "it", "r" (from R&D), "less" and "source".

O7's remaining known false positives are "It" at sentence start (4 jobs),
"Taleo" in application boilerplate and "operational excellence". The
implemented v3 reproduces these counts:
- ESCO switch off: 111 terms (the 96 above plus the 15 additional experience
  matches).
- ESCO switch on: 355 terms, 244 of them from the vocabulary.

Vocabulary terms add review workload, so they enter as `pending` evidence like
every extraction. Existing jobs are not re-extracted by this decision. Any
re-extraction must preserve review decisions; see the follow-up entry.

## D039 - Existing Jobs Are Re-extracted Additively

Existing jobs are moved to a new extraction contract (D038) by additive
reconciliation, never by the delete-and-recreate path used when a job is
created or edited. Command: `python -m app.services.job_service reextract`.
It is a read-only dry-run unless `--apply` is given. `--esco on|off` overrides
the config switch.

Stored and fresh occurrences match on (normalized text, term type, start,
end) in the stored cleaned text:
- **Matched occurrences keep their review:** review status, approved taxonomy
  links and suggestions stay as they are. A still-`pending` skill takes a
  changed requirement type. An approved skill takes it only from `unknown` to
  `required` or `preferred`: v2 never assigned a type there, so this fills a
  gap without overriding a reviewed value. Every other difference on an
  approved or rejected skill is reported for manual checking and not applied,
  e.g. preferred → required, required → unknown, or any rejected skill.
- **Reviewer-edited occurrences:** if a fresh term lands on the exact span of
  a stored occurrence whose text or type was edited during review, the stored
  occurrence is kept and the fresh term is not added. Otherwise re-extraction
  would re-introduce the raw text a reviewer corrected; the 2026-11-18 dry-run
  found 14 such cases.
- **New occurrences** are inserted as `pending` job skills with their
  versioned extraction method. Taxonomy linking runs for those term IDs only.
- **Vanished occurrences** (no longer extracted) are kept and reported.
- **Job create/edit** uses the same reconciliation instead of delete and
  recreate. In addition, an occurrence with the same text, type and evidence
  sentence at a new span counts as moved: its review is kept and its offsets
  are updated. Text removed by an edit leaves its occurrences in place,
  reported as vanished.

Each applied job gets an `additive_reextraction` processing log with the
counts. Its embedding is marked stale. `python -m app.retrieval.cli index
jobs` then re-embeds only jobs whose input hash changed.

The 30 Phase 5 evaluation jobs are included.

**Pre-apply snapshot (2026-11-18):**
- File: `skillgap-pre-job-reextraction-20261118T091512Z.dump`
  (PostgreSQL custom format), in `skillgap-snapshots/` beside the repository,
  not in Git.
- SHA-256:
  `141bcefaff08e2c6f82415a9c193228244cfdcb00f429d18c5d1a292ff12c94e`.
- State at the snapshot:
  - Alembic `0008_dense_retrieval`;
  - 118 extracted job terms and job skills (75 approved, 26 pending,
    17 rejected);
  - 41 approved job taxonomy links;
  - 30 ready job embeddings.
- Restore with
  `pg_restore --clean --if-exists -d skillgap <file>`.

Phase 5 results are unaffected. The accepted evaluation
`evaluation_v2_4ad60a9a219015141927c755` (source commit `d80e2c9`, template
`e5-job-profile-v2`, model `intfloat/multilingual-e5-small@fd1525a9`, 8
candidates × 30 jobs, 240 judgments) reported:

| Metric | Fraction | Value |
|---|---|---|
| Recall@5 | 37/84 | 0.440476 |
| Recall@10 | 53/84 | 0.630952 |
| Recall@20 | 5/7 | 0.714286 |
| MRR | 1261/1925 | 0.655065 |

Its ranking and metric files are immutable. The database state it was
produced from is preserved in the snapshot above. Re-running Phase 5 against
the live database after this re-extraction, and after reindexing, measures a
different system state.

The dry-run outputs reviewed before applying are in
`evaluation/local/job-reextraction-2026-11-18/` (git-ignored):
- `dryrun-esco-on-summary.txt` and `dryrun-esco-on-verbose.txt`: before the
  approved-unknown rule;
- `dryrun-esco-off-summary.txt` and `dryrun-esco-off-verbose.txt`;
- `dryrun-esco-on-verbose-final-rule.txt`: the plan that was applied.

Final plan, ESCO on: 31 jobs, 271 new pending terms (249 from ESCO), 9
approved unknown skills given a type, 19 reviewed differences reported only,
14 reviewer-edited spans kept and 2 vanished occurrences kept.

## D040 - Unlinked Job Skills Not Found By Name Count As Missing

This replaces the "could not be compared" rule of D036. An approved
skill-like job skill without an approved taxonomy link, and with no candidate
skill of the same normalized name, now counts as **missing**. It is included
in the X-of-Y totals. Each missing entry records how it was checked:
`checked_via` is `taxonomy_concept` (linked: looked for by concept, then by
name) or `skill_name` (unlinked: looked for by name only). The name-only chip
has the tooltip "Not found in your CV by name (may appear under a different
wording)", and the explanation lists those skills on a separate line. The
"could not be compared" category no longer exists.

Reason: excluding these skills shrank the denominator. A job could show
"1 of 1 matched" while several of its approved requirements were absent from
the CV under any wording. Showing them as missing, with the caveat, is the more conservative
reading for a decision-support tool. The cost is false "missing" results when
the CV states the skill in different words; the tooltip and explanation say so.

Ranking keys (D036), in order:
1. required coverage;
2. preferred coverage;
3. number of matched required skills, then number of matched preferred
   skills, more first;
4. retrieval similarity;
5. job ID.
Key 3 is new and applies only when both coverage fractions tie: 2 of 2 now
ranks before 1 of 1. It uses counts, not weights. Required comes before
preferred, as in keys 1 and 2.

There is no migration. `missing_required` and `missing_preferred` in
`candidate_job_matches` now hold `{label, checked_via}` objects instead of
bare labels. Rows are recomputed on every read. The response schema reads a
bare-label row from before this change as `taxonomy_concept`: under D036 only
linked skills could be missing.

## D041 - A Candidate Profile Combines All Of Its CVs

This records the current behaviour; nothing was changed. A candidate profile
can hold several CVs. Its skills are the union of:
- extraction skills from all of its CVs, whatever their processing status;
- skills the candidate added by hand during review (`source = manual_review`).
  These belong to the profile, not to one CV, and are shown in every CV's
  review list.

Both consumers use that union, and both read only **approved** skills:
- **Retrieval profile embedding:** `RetrievalRepository.profile_input` and
  `candidate_representation`. The text holds approved skills, with canonical
  labels and evidence, deduplicated. The source hash covers every skill row of
  the profile, including pending and rejected rows. Any added, changed or
  removed row therefore makes the embedding stale, even when the text is
  unchanged.
- **Skill-coverage matching:** `list_matchable_candidate_skills`. A skill
  listed in two CVs counts once, because coverage compares sets of concepts
  and names.

**Deleting a CV** (`CvService.delete_my_cv` →
`DocumentRepository.delete_cv_document`):
- deletes that CV's extracted terms, extraction skills and taxonomy links or
  link candidates, together with the document and its sections;
- marks the profile embedding stale;
- deletes all of the profile's stored match rows. They are recomputed on the
  next read, from the remaining CVs and manual skills.

Skills from other CVs and manually added skills stay. Taxonomy review audit
events stay, because they are append-only. The deletion itself is logged.

Reason for keeping this: one profile is the unit of decision support and of
the Phase 5 benchmark, and the union is the simplest rule a candidate can
predict. Per-CV profiles would need a choice of active CV, which the
candidate-facing flow does not have.

## D042 - CV Extraction Does Not Get The ESCO Vocabulary (Known Asymmetry)

Job extraction v3 (D038) adds the O7-filtered ESCO vocabulary and experience
ranges. CV extraction stays on contract v2: the 25-entry curated dictionary
plus regex rules. **This asymmetry is a known limitation.** A job can list an
ESCO-labelled skill that the CV states in the same words, and it is still
reported missing unless the candidate approved or added that skill.

Diagnosis (2026-11-18, in memory, no writes):
- **Method:** the 8 evaluation candidates' CVs were run through the
  extractor with the O7 vocabulary, the same filter and the same rule that
  dictionary matches win on overlap. Auto-linking used the production rule
  (rank 1, unique top, confidence ≥ 0.95).
- **New terms:** 56 unique terms (78 occurrences); 55 would be auto-linked.
- **Coverage gain:** even if every new term were approved, only **70 of
  1,275** currently missing job skills would become matched, **5.5%**.
  "Missing" counts each candidate × job × missing skill across the 30
  benchmark jobs. The gains fall almost entirely to four engineering
  candidates on the electronics, firmware and robotics jobs.

False-positive types seen:
- **Degree and field-of-study names read as skills** ("electrical
  engineering", "electronics", "electronic systems", "informatics"). One
  candidate's whole gain (10 matches) came only from degree lines. Jobs have
  the same effect, so these matches are often qualification against
  qualification rather than skill against skill.
- **Role descriptors and earlier job titles** ("instrumentation engineering").
- **Partial spans** ("system design" from "embedded-system design", "ide" from
  "STM32Cube IDE").
- **Singular/plural near-duplicates** ("pcb"/"pcbs", "control
  system"/"control systems").

Decision: **CV ESCO re-extraction is not implemented.**
- The gain is small, and its share of false positives is high.
- Any CV re-extraction would change all 8 frozen Phase 5 candidate inputs.
  New pending rows change the source hash. Once approved, they change the
  profile text.
- The existing CV reprocess path (`replace_candidate_terms`) deletes
  occurrences no longer extracted, with their reviews. A safe version would
  need an additive path like D039.

The evaluation candidate profiles are **largely manually curated**. Across the
database there are 107 approved manually added candidate skills and 79
approved extracted ones. All 107 manual skills belong to the 8 evaluation
profiles, which hold only 30 approved extracted skills. For the benchmark, CV extraction quality therefore matters less
than reviewer curation, as the Phase 5 limitations already state. If CV
vocabulary matching is revisited, degree and education lines must be handled
first, for example by typing those matches as qualifications or skipping
education sections. The same handling should then be checked on jobs.

## D043 - Matching Variants Are Compared Offline Without Weights

The ranking options are compared offline on the frozen Phase 5 benchmark. They
are not tuned in the app. `python -m app.retrieval.cli compare-matching` is
read-only:
- it opens a read-only transaction and rejects any write statement;
- it persists nothing in the database.

It ranks the same 30 jobs for the same candidates with four variants:
- **A:** retrieval only (cosine similarity);
- **B:** skill coverage with name matching only;
- **C:** skill coverage with taxonomy concept first, then name (the current
  rule);
- **D:** C with retrieval similarity as the tie-break (the current app).

All four are scored against the same frozen judgments and evaluable queries,
with the Phase 5 metrics plus nDCG@10 over grades 0/1/2. The rankings are
written in the Phase 5 format, so variant A also serves as the input to the
committed `evaluate` command.

**No hand-picked weights.** Each variant is either a single score (A) or a
lexicographic order of exact fractions and counts (B to D, D036/D040).
There is no parameter to choose, so nothing can be fitted to these judgments.
- A weighted blend, such as α·similarity + β·coverage, would need its weights
  chosen. With seven evaluable queries, choosing them on this benchmark would
  overfit it.
- Choosing them without data would repeat the arbitrary 2:1 weights that D036
  removed.

Results (`docs/verification/matching-variant-comparison.md`) are
descriptive only: no significance claims at n = 7. They also show that coverage
ranking is decided by ties for half of the candidates, so changes to the
coverage rule should not be judged on these numbers alone. Final Phase 6
scoring must still be configurable and versioned. Any future weight must come
from data other than this benchmark, or be declared before it is measured.

## D044 - Retrieval Ranks, Coverage Explains

(Superseded by D045 on 2026-11-21: retrieval now returns the top-N jobs
instead of ordering every active job; jobs without a current embedding are no
longer listed last but are not retrieved.)

The Jobs page orders jobs by Phase 5 retrieval similarity: variant A of D043.
This replaces the lexicographic coverage order of D036/D040.

Rules:
- Ties fall to job ID.
- A job without a fresh similarity goes last. This covers a missing or stale
  job embedding, and every job when the candidate's profile index is missing
  or stale.
- "#N of M" is the position in this order.
- The skill-coverage panel is unchanged: matched and missing skills, X of Y
  counts, and the explanation. It explains each job and no longer affects the
  order.
- The similarity value is still not displayed.

Evidence: the offline comparison on the frozen Phase 5 benchmark
(`docs/verification/matching-variant-comparison.md`), macro averages over the
7 evaluable queries:

| Variant | Recall@5 | Recall@10 | Recall@20 | MRR | nDCG@10 |
| --- | --- | --- | --- | --- | --- |
| A retrieval only | 0.512 | 0.595 | 0.857 | 0.620 | 0.703 |
| B coverage, name only | 0.107 | 0.310 | 0.548 | 0.151 | 0.306 |
| C coverage, concept then name | 0.107 | 0.310 | 0.548 | 0.150 | 0.317 |
| D coverage + similarity tie-break (former app) | 0.107 | 0.214 | 0.643 | 0.154 | 0.382 |

A leads on every macro metric. Per query, the exception is Q6: B to D place
its relevant job at rank 9 to 11, against 19 for A. Q6 is one of the
zero-match candidates, so that comes from the tie order and the
"has required skills" flag, not from matched skills.

Limits of this evidence:
- n = 7, one rater, no significance test.
- For 4 of 8 candidates, coverage matched no skill in any benchmark job. The
  coverage ranking there was decided by ties.
- The labels judge overall fit, not skill coverage.

The decision rests on that ranking signal being the better-measured one. It
makes no claim that coverage is wrong as an explanation.

There are still no weights. A is a single score, and coverage is no longer
combined with it. Choosing A on this benchmark is a selection between four
fixed variants, not fitting. The Phase 5 limitations still apply: no
generalization to hiring accuracy, and this is not an automated decision.
Final Phase 6 scoring must still be configurable and versioned.


## D045 - Final Matching Design: Top-N Retrieval, Coverage Explains

Decided by the project owner on 2026-11-21. This is the final matching design.
It supersedes the ranking rule of D044 and retires two earlier designs:
- the MASTER_PLAN Phase 6 weighted formula (0.35 semantic similarity, 0.35
  required coverage, 0.15 preferred coverage, 0.10 occupation, 0.05
  qualification/experience, critical-skill penalty);
- the `phase6-explainable-matching` branch design (its D034 policy
  `matching-policy-v1` with 7:3:2:1 structured weights, and D035). That branch
  is not merged, and its migrations 0009–0011 are not part of this line.

Rules:
- Phase 5 retrieval returns the top-N active jobs for the candidate's profile
  by exact cosine similarity. N is `RECOMMENDATION_TOP_N` (default 50; 100
  since D059).
- That order is the ranking. "#N of M" is the position among the M retrieved
  jobs (M ≤ N).
- Each retrieved job is explained by skill coverage under the existing rules
  (D036, D040): required and preferred "X of Y matched", matched and missing
  labels, and how each was checked. Coverage never changes the order.
- Similarity stays an internal value and is not displayed.
- Jobs without a current embedding are not retrieved. Their number is reported
  ("N active jobs are not yet indexed").
- If the candidate's profile cannot be used (no consenting profile, no
  approved skill, no up-to-date embedding, or model artifacts missing), the
  Jobs page shows a notice with the reason and no ranking.

Relation to D009/D022: retrieval still only selects and orders jobs. There is
no match score, weighted or otherwise. Coverage is an explanation, not a
score component. Still no weights, so nothing is fitted to the Phase 5
benchmark (D043). The frozen Phase 5 baseline is unchanged (D032).

## D046 - Profiles And Jobs Are Re-embedded Automatically After A Change

Decided by the project owner on 2026-11-21. Before this, any change made a
vector stale until an operator ran `python -m app.retrieval.cli index`, and the
Jobs page silently lost its ranking in the meantime.

- Every per-profile or per-job invalidation (`invalidate_profile`,
  `invalidate_job`, `invalidate_term`) records the owner on its database
  session. When the session commits, those profiles and jobs are re-embedded
  synchronously, in a separate session, with the same pinned local E5 model
  and the configured template (`app/retrieval/auto_reindex.py`). A rollback
  discards the record.
- That covers CV and job processing, extraction review, taxonomy link review
  and auto-linking, job edits and archiving, and CV deletion, because each of
  them already invalidates.
- Release-wide invalidation (`invalidate_all`, after a taxonomy import or
  release replacement) is not re-embedded automatically. Bulk runs stay with
  the `index` CLI, whose sessions never trigger automatic re-embedding.
- If the model is not provisioned, nothing is embedded and the request still
  succeeds. The vector stays stale, and the Jobs page says so. An encoding
  error marks that vector `failed`, as the CLI does.
- `AUTO_REINDEX=false` restores CLI-only behaviour.

The model is loaded once per backend process, on first use, so the first
change after a restart takes a few seconds longer. Re-embedding is serialized
by a process lock. Vectors are computed exactly as the CLI computes them
(same input text, hash, model revision and template), so the CLI's
idempotence check treats them as current. The frozen Phase 5 evaluation
artifacts are files and are not affected; live vectors of the evaluation
profiles and jobs change only if those records are edited.

## D047 - Candidates Can Delete Their Account And Data

Decided by the project owner on 2026-11-21. A candidate can delete their own
account with password confirmation (`POST /auth/delete-account`). In one
transaction it removes the user, role assignments, refresh tokens, candidate
profile, CVs, sections, extracted terms, all candidate skills (extracted and
manual), taxonomy link suggestions and selected links for those terms, the
profile embedding, stored match rows and processing logs about the profile or
its CVs. Deletes are explicit rather than relying on database cascades.

This changes D024's retention of taxonomy review events for this case: on
account deletion the review events of the candidate's own terms are deleted
too, because the account they describe no longer exists. Ordinary CV deletion
still keeps them (D024, D041).

Accounts with an administrator or researcher role cannot use this route.
Their review decisions on other people's records are attributed to them;
removing them is an administrative action.

## D048 - Candidates Review Taxonomy Links On Their Own Skills

Decided by the project owner on 2026-11-21. A candidate can approve or reject
the taxonomy link suggestions for the extracted terms of their own CVs
(`GET/PUT /cvs/{cv_id}/taxonomy-links[/{candidate_id}]`). Ownership is checked
through the term's CV and the candidate profile; anything else returns 404.
Candidates choose among the existing suggestions only; free concept correction
stays a staff action. The same review rules apply as for staff (one selected
link per term, explicit confirmation with a selection token to switch, review
events appended). Candidate approvals are stored with approval source
`candidate_review` and the candidate as approver, so they can be told apart
from staff `human_review` decisions in evaluation. Staff review is unchanged
and can still override a candidate's choice.

## D049 - Job Matching Is Candidate-Only And Computed On Read

Decided by the project owner on 2026-11-21. All `/matches` routes require the
candidate role and refuse administrator and researcher accounts, so
per-candidate rankings stay with their candidate (consistent with D037).
Retrieval and skill coverage are computed when read and are not stored:
`GET /matches/recommendations` and `GET /matches/jobs/{id}` write no rows.
The `candidate_job_matches` table is no longer written; the owner approved
dropping it, and migration 0009 removes it (D052). Explanations therefore always derive from the
current approved skills and links.

## D050 - Related Skill Via A Shared Specific ESCO Broader Concept

Decided by the project owner on 2026-11-21 (wording revised the same day).
Coverage classes are Matched, Related and Missing; the UI label for Related is
"Related skill in your profile" (AGENTS.md's "Partially Covered"). A
concept-linked job skill that is not matched is related when it and a
concept-linked candidate skill have a common direct ESCO `broader` concept
whose type is `skill` or `knowledge`, in the active ESCO release. Broader ESCO
skill groups do not count: in ESCO 1.2.1 they have a median of 13 and up to 217
member skills, and on the 2026-11-21 development data they accounted for 145
of the 185 entries an "any shared broader concept" rule would have changed.
With the specific-parent rule, 40 entries (22 required, 18 preferred) in 36 of
341 profile-job pairs change from Missing to Related.

Related skills are not counted as matched ("X of Y matched" keeps its meaning;
Y includes them). The explanation reads "<job skill>: not in your CV, but
related: you have <candidate skill> (same ESCO area: <broader concept>)", built
only from stored links and release relationships. Name-only skills and O*NET
concepts are never related. Coverage still never changes the order (D045). The
offline comparison (D043) is unchanged because it does not supply broader
relationships. API field names stay `partial_required`/`partial_preferred`.

## D051 - No Per-CV "Use For Matching" Switch

Decided by the project owner on 2026-11-21. The proposed per-CV switch
(`cv_documents.use_for_matching`) is rejected for simplicity. All of a
candidate's CVs and manual skills feed matching (D041); a candidate who does
not want a CV used deletes it, and the "Your matching profile" box shows what
is included.

## D052 - Job Sources And The Fixed Evaluation Set

Decided by the project owner on 2026-11-21. Every job has a `source`:
`evaluation` (the fixed 30-job evaluation set), `manual` (created in the app)
or the name of a live source adapter (`arbeitnow`, `greenhouse`, ...). Live
jobs carry `external_id`, `external_url`, `posted_at`, `last_seen_at` and a
`content_hash`; `(source, external_id)` is unique. Migration 0009 adds these
columns, keeps every existing job as `manual`, and drops the unused
`candidate_job_matches` table (D049). The evaluation jobs are identified only
by the private evaluation mapping, so they are tagged by a separate command
(`python -m app.job_sources.cli mark-evaluation-jobs --mapping ...`) that
changes nothing but `source` and refuses unless exactly 30 existing manual or
evaluation jobs are listed. Job text, skills, reviews and embeddings of the
evaluation set are not modified by tagging.

## D053 - Live Job Sources: Public APIs Only, English, Europe Or Remote

Decided by the project owner on 2026-11-21. Live jobs come only from public
job APIs through one adapter interface (`app/job_sources`): the Arbeitnow job
board API (no key) and the Greenhouse job board API (`content=true`, one public
board per company). Sites without an API are not scraped. Requests use a
generic user agent, at least 1.5 s between requests to one host, and bounded
retries that honour `Retry-After`. Each job keeps its original posting URL,
and the job page shows the source (Arbeitnow's terms ask for a link back).

Only English postings are imported, by a stopword-count check on title plus
description; other languages are skipped and counted per language (a board's
own `language` field is not trusted: on 2026-11-21 two N26 postings marked
`en` were German). By owner choice of EU-hiring or remote companies, postings
must also be located in the EU/EEA, UK or Switzerland, or remote without a
non-European region named; Arbeitnow, a Europe-focused board, is exempt
because its locations are mostly small towns. At most `LIVE_JOBS_MAX_ACTIVE`
(default 1,500) live jobs are active, newest posting date first.

The starter Greenhouse list (`GREENHOUSE_BOARDS`, 20 boards, each verified on
2026-11-21 to return jobs) covers engineering, data, finance/operations and
support roles: gitlab, elastic, grafanalabs, canonical, datadog, mongodb,
twilio, celonis, contentful, commercetools, stripe, adyen, sumup, n26, monzo,
tide, raisin, hellofresh, wolt, intercom.

## D055 - Live Job Import: Dedupe, Contact Removal And Archiving

Decided by the project owner on 2026-11-21. The import (CLI
`import-live-jobs`, the administrator "Run import" button, or an optional
daily Compose service) runs one at a time and:

- removes contact details from every description before anything is stored:
  e-mail addresses, phone numbers (8-15 digits with an international or trunk
  prefix) and a personal name directly after a contact cue ("Recruiter:",
  "reach out to", "Ansprechpartnerin", "contact op met", ...). Whole contact
  lines are not dropped: on 2026-11-21 that removed ordinary sentences;
- dedupes by `(source, external_id)` and by a hash of title, company and
  description, so the same posting under another ID is skipped;
- runs the existing job pipeline (sections, extraction v3, taxonomy linking)
  for new or changed postings; changed postings use additive re-extraction
  (D039), so reviews are kept;
- sets `last_seen_at` on every posting still listed, archives live jobs not
  seen for `LIVE_JOBS_ARCHIVE_AFTER_DAYS` (default 14) and the oldest beyond
  the cap. A failed fetch therefore archives nothing until the window passes.
  A job archived by the import comes back when listed again; one archived by
  staff stays archived;
- embeds changed jobs once at the end (D046 is paused during the import
  because each job commits more than once).

Each run is stored as a `job_import` processing log with all counts.
Manual and evaluation jobs are never changed by the import.

## D054 - Unreviewed Skills On Live Jobs Count For Coverage, Flagged

Decided by the project owner on 2026-11-21. This narrows D036's approved-only
rule for job skills. On live jobs (any source other than `manual` and
`evaluation`), pending skills are used for coverage, because about 1,500
postings cannot all be reviewed; rejected skills are never used. Every
coverage entry that rests only on unreviewed occurrences carries
`reviewed: false`, the Jobs page shows it with a dashed outline and the note
"automatically extracted, not reviewed", and the explanation lists those
skills. Manual and evaluation jobs keep approved-only coverage, and the
offline comparison (D043) is unchanged. Candidate skills stay approved-only.
Administrators can still review live job skills; an approved occurrence makes
the skill reviewed. Job embeddings already included pending skills (only
rejected ones are left out), so retrieval is unchanged. In the job skill
panels (candidate and staff) and the staff taxonomy review queue, pending
skills and link suggestions of live jobs are labelled "automatic" instead of
"pending" (wording only; the stored status stays `pending`).

## D056 - Candidate Job Scope And Evaluation-Set Isolation

Decided by the project owner on 2026-11-21. Candidates (Jobs page
recommendations, single-job coverage, `GET /jobs`, `GET /jobs/{id}` and
`GET /retrieval/jobs`) see active manual and live jobs only. Evaluation jobs
are left out unless `CANDIDATE_VIEW_INCLUDES_EVALUATION_JOBS` is true;
administrators and researchers see every job. The offline benchmark and the
coverage-ordering comparison (D043) search only `source = evaluation`, so live
jobs added later cannot change their results; `retrieval index jobs --source
evaluation` re-indexes only that set. The filter is applied in the exact
vector search itself, so top-N is taken within the allowed sources.

## D057 - Live-Job Link Suggestions Are Not In The Default Review Queue

Decided by the project owner on 2026-11-21. The first live import left
20,184 pending taxonomy link suggestions on live jobs, which would bury the
suggestions staff are expected to review. The staff review queues
(`GET /taxonomy/reviews`, `GET /admin/mappings/review`) therefore default to
`scope=default`: CV terms and terms of manual and evaluation jobs.
`scope=live` lists only live-job terms and `scope=all` lists everything; the
Taxonomy page has a selector for this. A lookup by extracted term ID ignores
the scope. Live-job suggestions are kept and stay reviewable; high-confidence
deterministic matches are still approved automatically, and coverage on live
jobs uses those links as before (D054).

## D058 - Per-Source Share Of The Live-Job Cap

Decided by the project owner on 2026-11-21. The cap kept the newest postings
across all sources, and Arbeitnow postings are usually newer, so the first
import held 911 Arbeitnow and 66 Greenhouse jobs. No source may now hold more
than `LIVE_JOBS_MAX_SOURCE_SHARE` (default 0.7) of `LIVE_JOBS_MAX_ACTIVE`,
that is floor(share x cap). Postings are taken newest first; a posting is
skipped once its source is full, so other sources fill the remaining places
and the cap can still be reached. The same rule decides which active live
jobs the import archives (oldest of a source beyond its share). It applies
from the next import; with the current data that import archives the oldest
Arbeitnow jobs above 70 % of the cap. 1.0 switches the limit off.

## D059 - Jobs Page: Top 100, Shown In Pages

Decided by the project owner on 2026-11-21. With live jobs the candidate Jobs
page retrieves the top 100 jobs by similarity (`RECOMMENDATION_TOP_N` default
100, was 50) and shows them in pages: 10 per page by default, 10, 25 or 50
selectable (`page`, `page_size` on `GET /matches/recommendations`). The header
reads "Showing X-Y of N best-matching jobs". "#N of M" stays the overall
retrieval rank among the M retrieved jobs on every page. Skill coverage is
computed only for the jobs on the requested page. Order and coverage rules
are unchanged (D045). Job representations used for the freshness check of
retrieved jobs are memoized in process by a digest of their exact inputs; the
build is a pure function of those inputs and the pinned tokenizer, so results
are identical and any change to a job, its skills, links or sections is a new
key. At startup a background thread fills this cache for every job with a
ready vector (`WARM_JOB_CACHE_ON_STARTUP`, default true); it pauses while any
request is in flight and changes nothing in the database.

## D060 - Relevant Experience: Self-Entered, Explained, Optionally Filtered, Never Scored

Decided by the project owner on 2026-11-21, after a read-only feasibility
check: on the development CVs, only 4 of 15 yielded dated work entries and none
of their titles linked to an ESCO occupation, so experience is not parsed from
CVs for matching.

- **Self-entered.** Candidates enter work entries on the CVs page: job title,
  start month, end month or "present", and an ESCO occupation they pick from
  the top 5 suggestions for the title (or none). Dates found in a CV only
  pre-fill the form; nothing is stored until the candidate adds the entry.
- **Job side.** The minimum required years are parsed from the job text on
  read (first requirement mention; number words; company-age, retention,
  benefit and preference phrases dropped; rule in
  `app/matching/experience.py`). The job occupation is the cleaned title linked
  with the existing automatic-approval rule; otherwise "occupation not
  determined". Evaluation jobs are never linked or assessed.
- **Relevance.** An entry is related when its occupation and the job's share
  the 3-digit ISCO group; overlapping periods are merged and the months
  summed. The check showed 4 digits too narrow (data scientist 2511 vs software
  developer 2512) and 2 digits too broad (chemists with civil engineers).
- **Explanation, not a score.** The job card shows "About N years in related
  roles (ISCO xxx ...) · job asks M+ years → meets / below requirement" only
  when the job has a minimum and an occupation and the candidate has entries
  with an occupation. It never changes the retrieval order (D045) and is not
  combined with similarity or coverage.
- **User-chosen filter.** "Hide jobs where my related experience is below the
  requirement" is off by default, remembered per candidate, and applied before
  the top-N cut. Jobs without a minimum or a determined occupation are never
  hidden. Only the candidate turns it on; it is never applied for them.
  With the filter on, "#N of M" counts only the jobs shown; the relative
  order of the remaining jobs is the retrieval order.
- **Fairness.** Years of experience correlate with age, which must not affect
  matching (AGENTS.md). Experience therefore never ranks or scores jobs; it is
  shown against the job's own stated requirement and filters only at the
  candidate's request. Unrelated personal attributes are not collected.
- **Data minimisation.** No employer, location, description or reference is
  asked for or stored; only title, months and the chosen occupation. Entries
  are visible to the candidate only, editable and deletable, and removed with
  the account. Staff cannot read them.
- **Isolation.** The offline evaluation is unchanged: it never passes the
  filter, evaluation jobs get no occupation or minimum, and the evaluation
  profiles have no work entries.
- **Rejected: group agreement.** Assigning a 3-digit ISCO group to job titles
  without an automatic occupation when their top-3 occupation suggestions
  share that group was checked read-only on 977 live jobs (2026-11-21) and
  rejected. It covered only 20 more titles (ISCO group 23.5% -> 25.6%;
  minimum and group 10.1% -> 11.6%), and 5 of the 20 were wrong: the three
  suggestions shared only the generic word "engineer" ("Senior/Lead Python
  Engineer", "Full Stack Engineer" -> 214 Engineering professionals). Most
  suggestions were weak fuzzy matches (18 of 20 below 0.80), and no
  confidence threshold separated right from wrong.
- **Rejected: automatic embedding-based job occupations.** Linking cleaned
  job titles ("query:") to the nearest ESCO 1.2.1 occupation label
  ("passage:", 3,039 preferred + 30,156 alternative labels) with the pinned
  E5 model was checked read-only (2026-11-21) and rejected for jobs. On the
  230 auto-linked live jobs it agreed at 3 digits 230/230 and at 4 digits
  156/230 (67.8%), but that key is easy (exact label matches). It gave every
  one of the 747 unlinked titles a group (minimum and group 10.1% -> 43.8%),
  yet only 9 of 20 random examples were plausible ("Senior Quantitative
  Researcher" -> quantity surveyor; "AI R&D Engineer" -> animal artificial
  insemination technician at similarity 0.930). Similarities are compressed
  (80% of unlinked titles between 0.869 and 0.931) and wrong matches score as
  high as right ones, so no threshold helps. Cost: 51 s one-off label
  embedding, about 118 ms per title. Embedding neighbours are used only as
  extra suggestions in the candidate's work-entry form, where the candidate
  picks an occupation or none.
