# Phase 6 Explainable Matching Policy

Status: **ACCEPTED METHODOLOGY** on 2026-11-10 after independent review.

Acceptance freezes `matching-policy-v1` methodology before implementation and
before Phase 6 rankings. D034 records the accepted decision. This is a design
checkpoint, not a completed Phase 6 implementation. Checkpoint 1 is committed
at 2c77df0. Checkpoint 2 implements retrieval-to-result orchestration and is
uncommitted for independent review, with new migration 0010; applied migration
0009 is not edited. No real or frozen-corpus Phase 6 facts, inventory sign-offs,
scores, rankings or evaluations have been created. Synthetic tests use isolated
databases only. Fact entry and execution require separate authorization.

## Proposal Revision History

This documentation-only revision incorporates the accepted independent-review
corrections. The preceding 425-line draft had SHA-256
`bc25b888a41b149efd709dfafa58e4d9d75d5c45720a5b349bede299c6ae41ad`.
It is superseded, not represented as an implemented or approved policy. The
revision replaces the mean critical penalty with a maximum, tightens inventory,
identity and readiness rules, removes eligibility, specifies relational
persistence, and moves corpus methodology to `phase6-evaluation-protocol.md`.

The next documentation-only correction pass supersedes policy SHA-256
`e53c8316489ad55375696383d88324bdfa841cd82258138419114a0632c0aa77`.
It defines identity comparability/reasons, corrects Recall@20 subset
interpretation, names the cutoff metric MRR@20 with a retrieval-order baseline,
preserves minimal reviewer attribution, makes Q-fact membership exclusive, and
removes speculative future-relationship implementation requirements. Neither
revision is an implementation or approval record.

Accepted pre-promotion policy SHA-256:
`3c453b660d80c7f1521a26548737048c58c00dcb3825f9ab994383551e4a5d8c`.
The accepted pre-promotion evaluation protocol SHA-256 was
`33f97280dca56a9d8d15f861facfc7e515a748534dcc815a778131aa1557c3fc`.
Promotion records acceptance on 2026-11-10 without changing the reviewed
methodology or its implementation boundaries.

Checkpoint 1 implementation additions (2026-11-11) introduced the pure engine,
migration/table contracts and reviewed-input API documentation. The preceding
accepted repository document SHA-256 was
`f30b40dacb7579ef2fb97f44626bc4fe4196384b725e657944527e9be037d997`.
The implementation document before this acceptance-correction pass had SHA-256
`949a6b4502c17b1c25b7ac7000a806434cd6eef2581b412d8f4a880df51e876d`.
The corrections repair implementation conformance and storage/lifecycle guards;
they do not change matching-policy-v1 methodology, canonical configuration or
weights. Detailed runtime/test evidence belongs in PROJECT_STATE.md.

Checkpoint 2 implementation additions (2026-11-12) connect the accepted engine
to owned explicit runs, exact persisted components/gaps and bound evidence,
retrieval provenance, concurrency and read-only currentness checks. The preceding
repository document SHA-256 was
`2380f868eaedf63775d405ee100bb624726e6e6e62111f62256205fccfe18307`.
Migration 0010 extends persistence/invalidation guarantees without editing 0009.
No matching-policy-v1 configuration, weights or methodology changed. See
PROJECT_STATE.md for tested/deferred functionality and verification results.

## Baseline And Scope

- Audit branch: `phase6-explainable-matching`.
- Audit HEAD and frozen Phase 5 checkpoint:
  `349e668f670f71dadfa7d4680fdcb1ceef334321`.
- Git was clean when the read-only policy audit was completed.
- Original methodology baseline: `0008_dense_retrieval`. Checkpoint 1 repository
  head: `0009_explainable_matching`. Checkpoint 2 repository head is
  `0010_matching_input_integrity`. The developer database was separately migrated
  to 0009 before Checkpoint 2; it is not accessed or migrated by this checkpoint.
  See PROJECT_STATE.md for historical audits and current verification results.
- Phase 5 is complete and frozen. Its model, Template-v2 representations,
  embeddings, rankings, judgments and results must not be retrospectively tuned.
- The early `MatchingService` and `candidate_job_matches` implement a lexical
  prototype, not this methodology. Preserve legacy rows and keep final runs
  and results separate.
- The application remains career decision support, not automated hiring or
  candidate selection. Do not use irrelevant personal or protected attributes.
- Policy v1 has no eligibility component. Work authorization, citizenship,
  residency, age and other protected or personal attributes are never
  collected, assessed or displayed by matching.

The architecture remains routes -> services -> repositories -> domain/database
components. Routes stay thin. The methodology sections specify the accepted
contract; checkpoint sections distinguish implemented and deferred behavior.

## Plan Mapping And Intentional Departure

`MASTER_PLAN.md` identifies required/preferred skill coverage, occupation
alignment, qualification/experience alignment, semantic similarity and a
critical-skill penalty. Its initial draft assigns semantic similarity 35%.

**Dense numeric weight zero is an intentional departure from that draft's 35%
semantic component and is recorded in accepted D034.** Similarity stays
disclosed retrieval evidence, never a numerical contribution to alignment. It
may influence ties only through the original retrieval order.

Remove the semantic weight and preserve the remaining draft proportions:
`0.35 : 0.15 : 0.10 : 0.05 = 7 : 3 : 2 : 1`. This is a declared methodological
prior, not an empirically optimized or validated weight configuration.

| Component | Base Weight | Exact MASTER_PLAN Requirement | Assessment |
| --- | --- | --- | --- |
| R | 7 | Required skill coverage | Mean support across approved required occupational-skill groups. |
| P | 3 | Preferred skill coverage | Mean support across approved preferred occupational-skill groups. |
| O | 2 | Occupation alignment | Reviewed same-concept occupation identity, explicit reviewed incompatibility, or unknown. |
| Q | 1 | Qualification/experience alignment | Equal-weight mean of applicable reviewed qualification and scoped-experience requirement groups. |

Experience is explicitly scored inside Q, not an implicit or separately weighted
fifth component. Qualifications and experience must not also count in R/P.
There is no standalone seniority scoring or assessment component. Explicit
experience duration and scope belong in Q; other seniority observations remain
evidence-bound caveats only. Titles alone are not scored.

## Mathematical Policy

For each component i, report:

- applicability a_i: `applicable`, `not_applicable` or `unknown`;
- assessment coverage c_i;
- nullable component value C_i in [0, 1];
- base weight b_i and nullable final effective weight w_i.

Once applicability is resolved for every component, let A be the applicable
components. For i in A, `w_i = b_i / sum(b_j for j in A)`. A genuinely
inapplicable component has effective weight zero. Unknown applicability is not
silently omitted; it prevents an overall score and final effective weights.

```text
E = sum(w_i * C_i for i in A)
D = max(1 - support(g) for explicitly reviewed critical required groups g)
D = 0 if no reviewed critical required groups exist
Alignment = 100 * clamp(E - 0.10 * D, 0, 1)
```

The accepted 0.10 maximum critical deduction is a predeclared policy constant,
not a measurement. Required gaps already reduce R; the extra deduction applies
only to explicitly reviewed critical required groups. Preferred and unknown
requirements and non-requirements never receive this penalty. Any critical
group with unknown support makes the result provisional and prevents a
complete score. A maximum, not a mean, ensures adding satisfied critical groups
cannot reduce the penalty for an existing missing critical group.
Critical inputs without an applicable, non-empty required-skill component R
are invalid and rejected, not silently ignored.
No requirement becomes critical from
its taxonomy relation, occupation statistics, label or absence of evidence.

Use exact rational arithmetic throughout the policy engine. Store the exact
fraction string and a `NUMERIC(10,6)` projection for scores and fractional
component/support values; the projection is not the ordering authority. Order
by exact alignment descending, original retrieval rank ascending, then the
lowercase canonical job UUID string ascending. Display converts the exact
fraction using Decimal `ROUND_HALF_UP` to two decimal places, without an
intermediate rounded storage value. The result is an evidence-alignment index,
not a suitability probability or prediction of hiring success.

Exact strings use reduced signed-numerator/positive-denominator form, including
`0/1` and `100/1`. Database checks reject malformed/noncanonical fractions,
null/projection disagreement and disagreement with six-decimal rounding.
Provisional is exactly equivalent to a null alignment value. Component/support
values are null or in [0,1]; alignment is null or in [0,100].

## Evidence And Group Support

Only approved candidate occurrences/facts and approved job requirements may
contribute. Pending and rejected evidence never contributes to the final score.
Taxonomy approval does not approve an extraction occurrence. Candidate-approved
skills are **candidate-confirmed evidence**, not independently verified evidence;
explanations must use that wording.

Scoring accepts only these exact canonical values, without case conversion or
silent coercion:

- review status: `approved`, `pending`, `rejected`;
- requirement classification: `required`, `preferred`, `non_requirement`,
  `unknown`.

`non_requirement` is an explicit reviewed decision, not an inferred default.
Unrecognized stored values block readiness and require an explicit handling
plan, rather than being interpreted as approved, required or non-requirement.

Atomic occupational-skill support is:

- 1 when both sides have approved taxonomy links usable for identity in the
  same taxonomy release and their concept IDs match;
- 0 when those same-release linked concept IDs differ, even if labels match;
- 1 for conservative exact reviewed text-and-compatible-type identity,
  explicitly labelled `text-only`, attempted only when neither side has an
  approved taxonomy link usable for identity;
- 0 when no sufficient approved profile evidence supports the requirement.

A taxonomy link is usable for identity only if it is approved and belongs to
a release selected for matching in the run's fingerprinted taxonomy selection.
When only one side has a usable link, or the two sides' usable links share no
release, identity is incomparable. Atomic support is then 0, with reason code
`identity_incomparable`. The gap is shown as Missing with that reason code and
the candidate occurrence it concerns. It must never be explained as
"not evidenced in approved profile inputs". The result carries a readiness
warning, not a block. For a requirement, support is the maximum over all
approved candidate occurrences, each assessed independently under these rules.

Pending/rejected links are not identity evidence and cannot block text-only
fallback. Approved links outside selected comparable releases produce
identity_incomparable rather than being erased by matching text; that warning
does not block completeness.

Identity reason codes are distinct:

| Reason Code | Meaning |
| --- | --- |
| identity_match | Usable same-release links have matching concept IDs; atomic support 1. |
| identity_mismatch | Usable same-release links have different concept IDs; atomic support 0, without text fallback. |
| identity_incomparable | Only one side has a usable link, or usable links share no release; atomic support 0 with an occurrence-specific warning, not a claim of absent evidence. |
| text_only_match | Neither side has a usable link and permitted exact normalized text/type matching succeeds; atomic support 1. |
| not_evidenced | No approved candidate occurrence supplies support under an otherwise applicable comparison, including absence of candidate occurrences; not a replacement explanation for mismatched/incomparable identity. |

Retain the individual occurrence assessments and reasons even when another
occurrence supplies maximum support. Do not collapse an incomparable or
mismatched comparison into a generic not_evidenced explanation.

Text-only normalization is Unicode NFC, casefold and whitespace collapse,
with no punctuation stripping. `skill` and `tool` share the
`technical_capability` family and may text-match each other.
`domain_knowledge` matches only `domain_knowledge`; `language` matches only
`language`. Qualification and experience never enter R/P text-only matching
and must use Q facts. Every other type combination is unsupported.

Text-only matching never bridges different taxonomy systems or releases and
never overrides conflicting linked concepts. A one-sided usable link does not
permit text-only fallback. Incomparable or unusable identity evidence must be
reported explicitly; do not invent equivalence or silently erase an existing
link's release provenance.

Zero support with reason `not_evidenced` means **not evidenced in approved
profile inputs**, not that the candidate cannot perform the skill. Zero from
`identity_mismatch` or `identity_incomparable` keeps its distinct explanation.
A reported-use or supervised-practice
statement cannot satisfy an explicitly stronger mastery or independent-practice
requirement without suitable reviewed evidence. Preserve technical punctuation,
Unicode, source IDs and evidence caveats in conservative text matching.

Policy v1 supports one-level `SINGLE`, `OR` and `AND` groups over atomic members
only; no nesting. Deduplicate members by evidence/concept identity before
arithmetic, retaining all evidence references. Each job skill occurrence and
each reviewed Q-fact can belong to at most one R, P or Q scoring group.
Linked arithmetic members use the complete applicable approved concept-identity
set. Unlinked text-only members use `(text, compatibility_family, normalized_text)`;
distinct occurrence IDs do not create repeated credit. All occurrence references
remain in explanations. Incompatible type families do not deduplicate together.

- SINGLE: use the atomic member's support, including unknown.
- OR: support is 1 if any member is 1; otherwise unknown if any member is
  unknown; otherwise the maximum known support.
- AND: unknown if any member is unknown; otherwise the arithmetic mean over
  distinct members.

Groups must be non-empty; SINGLE has exactly one distinct member. Fractional
AND coverage can be Partially Covered without granting relationship credit.

Policy v1 requires `relationship_allowlist == []`; configuration validation
rejects any non-empty value. No future relationship implementation is required
by v1. In particular, there is no universal 0.5 broader-relation credit.
Broader, essential/optional, occupation-skill and cross-taxonomy relationships
are not automatically equivalence or possession evidence. Future enablement
requires separately verified semantics, a new policy version and a
corresponding implementation change.

Approved unlinked/manual skills can receive text-only support. They remain
candidate-confirmed evidence, not proficiency measurements. Different
releases/concepts do not collapse because their labels match.

For O, reviewed same-concept occupation identity gives 1; explicit reviewed
incompatible alignment gives 0; otherwise assessment is unknown. Different
titles or concepts alone do not establish incompatibility.

For Q, explicit facts may establish satisfaction or contradiction. Missing
degree-completion status, unbounded experience duration, unclear field or
equivalence, and unsupported experience scope yield unknown, not zero.
Preserve unfinished-degree and alternative-route wording. Do not add
overlapping periods blindly or infer seniority from a title. Q facts establish
supported satisfaction, contradiction or unknown support, not eligibility.

## Applicability, Coverage And Readiness

An approved unknown-classification job occurrence remains visible and unscored.
It creates coverage/readiness warnings, not required-skill penalties. It must
not silently become required or disappear from the explanation. A bound
approved occurrence with classification unknown blocks inventory sign-off.
Any bound occurrence still pending review also blocks sign-off.

Qualification and experience occurrences must be represented in Q groups or
explicitly reviewed as `non_requirement` before sign-off. Every bound approved
scoring occurrence must be accounted for in its R/P/Q group or explicitly
classified `non_requirement`; rejected occurrences remain retained but unscored.

A group classification cannot silently override the referenced JobSkill legacy
requirement_type. A differing classification needs an explicit approved
occurrence review with reason, reviewer/time, immutable attribution snapshots
and current source binding. Matching classifications need no override. Source
changes make an earlier override stale until explicitly reviewed again.

**Absence of pending extraction rows does not prove requirement-inventory
completeness.** Extraction can miss requirements. Require an explicit reviewed
job-level `inventory_complete` state, with reviewer/time and a binding to the
current job source and requirement inventory, before a complete score is
allowed. A source or requirement-inventory change invalidates that sign-off.
Reviewing the inventory does not require inventing manual extracted skills;
it explicitly establishes the reviewed scoring scope and any known omissions.

O and Q `not_applicable` decisions require a fixed reason code, reviewer
identity, `reviewed_at`, and binding to the reviewed inventory fingerprint.
Initial codes are `no_occupation_scope_stated` for O and
`no_qualification_or_experience_scope_stated` for Q. Absence of stored rows
never implies not_applicable. Undecided applicability is unknown and prevents
a complete score. Deletion of a reviewer must not silently make the review
appear to have had no attribution; retain a non-sensitive review snapshot.

Assessment coverage is the assessed group count divided by the identified
applicable group count for each component. Unresolved applicability or an
incomplete inventory must be reported separately; an apparent 100% over known
groups is not proof the inventory is complete. Applicable unavailable groups
have unknown support, not numerical zero. If there are no applicable groups,
coverage is not applicable rather than a fabricated success value.

An overall score is available only when all of the following hold:

1. Every component's applicability is resolved.
2. The explicit job-level inventory-complete sign-off is current.
3. At least one approved R or P group exists.
4. Every applicable component has 100% assessment coverage.
5. Source, review, policy and retrieval inputs are current.
6. No critical required group has unknown support.

Otherwise return `alignment_score=null`, `provisional=true`, available component
assessments and deterministic readiness reason codes. Do not publish a
reduced-denominator score by dropping an unavailable component. Bound pending
occurrences and bound approved unknown-classification occurrences prevent
inventory completeness. Unknown-classification rows are not penalties or
automatic requirements.

Minimum candidate/job fact-review inputs for non-null scoring are:

- an authorized candidate profile with approved current evidence supporting
  the assessment scope; pending/rejected rows remain excluded and scope
  warnings are preserved;
- at least one approved job R/P group and a current explicit job inventory
  review, including group membership, alternatives, canonical classification,
  complete accounting of bound occurrences and inventory-complete sign-off;
- reviewed applicability of O and Q: either genuinely not applicable, or the
  candidate/job occupation, qualification and scoped-experience facts needed
  to resolve every applicable group;
- attributed, timestamped, inventory-bound reason codes for any O/Q
  not_applicable decision;
- sufficient review of completion, field/equivalence, duration and scope where
  those facts are required, rather than inference from keywords;
- explicit reviewed critical flags only where a penalty is intended; absent
  reviewed criticality means zero critical penalty;
- current, compatible embeddings and complete input provenance for the primary
  retrieval pipeline.

This does not require treating a candidate's approved skill list as an
exhaustive statement of ability. Skills absent from that list are not evidenced;
missing qualification/experience facts remain unknown. Current extraction
alone cannot establish the additional reviewed fact inputs.

## Canonical Configuration Example

```json
{
  "policy_version": "matching-policy-v1",
  "component_weights": {"required": 7, "preferred": 3, "occupation": 2, "qualification_experience": 1},
  "dense_numeric_weight": 0,
  "relationship_allowlist": [],
  "critical_penalty_cap": "0.10",
  "evidence_review_status": "approved",
  "unknown_requirement_policy": "visible_unscored",
  "readiness": "resolved_applicability_complete_inventory_full_assessment",
  "group_operators": ["SINGLE", "OR", "AND"],
  "nested_groups": false,
  "arithmetic": "exact_rational",
  "critical_aggregation": "maximum_missing_support",
  "retrieval": {"template": "e5-job-profile-v2", "primary_pool": 20},
  "tie_break": ["exact_alignment_desc", "original_retrieval_rank_asc", "lowercase_canonical_job_uuid_asc"]
}
```

Canonical configuration JSON, arithmetic/grouping rules and engine version
form the policy hash. Any substantive rule change requires a new immutable
policy version. The example is an accepted methodology contract, not an
existing API schema.

## Deterministic Explainability Contract

Overall result fields:

- `run_id`, `result_id`, job identity, nullable `alignment_score`, `provisional`;
- readiness/currentness reasons, assessment coverage and computation time;
- policy version/hash, engine version and complete input fingerprint;
- separate retrieval provenance: `original_retrieval_rank`, disclosed similarity,
  pool limit, model/revision/template, embedding/source provenance and a
  separate read-only count of stale/missing eligible job embeddings;
- eligible-universe completeness warning, score-ready/provisional job counts
  and ranking-evaluation readiness.

Each component returns applicability, assessment coverage, nullable value,
numerator/denominator, base/effective weight, contribution and rule IDs.
Numerical assessments carry exact fraction strings and NUMERIC projections.
Unresolved applicability means final effective weights are unavailable; expose
base weights and reasons rather than misleading completed contributions.

Each requirement assessment returns group/operator, classification,
criticality, review state, support, matched candidate occurrence references,
exact reviewed evidence references, concept/release identities, text-only
status, caveats and any enabled relationship provenance/direction. Gap states
are `Matched`, `Partially Covered` and `Missing`; unknown support is explicitly
unassessed, never forced into Missing or numerical zero.

Qualification and experience assessments expose their candidate-confirmed
facts, job requirements and support findings. Seniority observations are
caveats only. There is no eligibility field or assessment. Include missing required/preferred lists,
unassessed requirements and visible unknown-classification occurrences.
Versioned fixed reason codes/templates produce explanation text from stored
parameters and evidence. No LLM generates claims. Extraction confidence,
taxonomy confidence and matching support are distinct, not calibrated
probabilities.

## Migration 0009 (Checkpoint 1)

Implemented migration: `0009_explainable_matching`, after `0008_dense_retrieval`.
Do not edit applied migrations or reinterpret legacy `candidate_job_matches`.
The following logical schema is materialized in Checkpoint 1 and verified only
in isolated PostgreSQL, not applied to the developer database.

| Table | Purpose And Essential Constraints |
| --- | --- |
| scoring_configurations | Immutable policy version, canonical configuration/hash, engine contract and activation metadata; unique version/hash. |
| candidate_matching_facts | Candidate/profile FK ownership; occupation, qualification or experience fact type; completion/duration/field/scope columns where applicable; candidate-confirmed provenance, review status, evidence reference, reviewer FK SET NULL, immutable reviewer pseudonym/role snapshots and timestamps. No inferred legacy backfill. |
| job_matching_facts | Job-owned reviewed Q-fact records for qualification/experience group members, with typed completion/duration/field/scope requirements, evidence references, reviewer FK SET NULL, immutable reviewer pseudonym/role snapshots and review timestamps. |
| job_requirement_groups | Job FK; component R/P/Q; operator SINGLE/OR/AND; canonical classification; critical flag; reviewer FK SET NULL; immutable reviewer pseudonym/role snapshots; reviewed_at; source/inventory fingerprint. |
| job_requirement_group_members | Group FK and exactly one job_skill or reviewed job Q-fact reference; unique group/member; separate global partial unique indexes on non-null job_skill_id and non-null job_matching_fact_id so neither occurrence nor Q-fact can enter multiple scoring groups. |
| job_inventory_reviews | Job FK; canonical review status; explicit inventory_complete state; O and Q applicability/reason-code columns; reviewer FK SET NULL; immutable reviewer pseudonym/role snapshots; reviewed_at; bound job-source/inventory fingerprint. |
| job_occurrence_reviews | Phase 6-only per-occurrence classification/review and current source fingerprint with immutable reviewer attribution. Explicit non_requirement decisions do not rewrite Phase 5 JobSkill fields or embeddings. |
| matching_runs | Candidate/profile FK and policy FK; candidate, policy and universe/input fingerprints; relational status/current flag; pool limit, stale/missing eligible-job count and timestamps. |
| job_match_results | Run/job references and job/input fingerprints; nullable alignment fraction and NUMERIC value; provisional flag; status; original retrieval rank and similarity. Unique job per run. |
| match_score_components | Result FK; component/applicability/status; numerator, denominator, base/effective weight, value and contribution, including exact fractional forms; unique component per result. |
| skill_gap_results | Result/group/member references; nullable atomic/group support and exact fractional forms; critical flag, classification and assessment status; unique assessment per result and group/member scope. |
| skill_gap_atomic_results | Relational member/occurrence comparisons with nullable exact/numeric support and reason parameters, separate from the group support row. Checkpoint 2 writes these only through explicit owned run creation. |

Use UUID keys, timestamps, relational status/applicability enums and FK
constraints. Fields used in constraints or queries stay relational, including
candidate/job/policy/input fingerprints, nullable alignment, provisional state,
retrieval rank/similarity, component arithmetic/weights/values, nullable atomic
and group supports, critical flags and group IDs. Store canonical policy
configuration as canonical text plus its hash and queryable policy fields.
JSONB is limited to evidence snapshots and versioned reason-code parameters.
Store fixed reason codes and bound parameters on results/components/gaps;
there is no recommendation_explanations table.

Add a partial unique index allowing one active/current run per candidate and
policy. Lock the candidate-profile row during run creation, retire the previous
current run and install the new one atomically. Enforce group ownership and
component/classification compatibility, non-empty groups, SINGLE cardinality,
no nested groups and member-reference exclusivity. Require global partial
unique indexes `UNIQUE(job_skill_id) WHERE job_skill_id IS NOT NULL` and
`UNIQUE(job_matching_fact_id) WHERE job_matching_fact_id IS NOT NULL`, in
addition to group/member uniqueness. Thus each occurrence and each reviewed
Q-fact belongs to at most one scoring group. Critical flags are valid only on
reviewed required groups.

Every reviewed table whose reviewer FK can become NULL must retain immutable
`reviewer_pseudonym_snapshot` and `reviewer_role_snapshot` fields captured at
review time. These preserve only the minimum non-sensitive attribution required
by the audit methodology, not credentials, email addresses or full identity
details. Reviewer deletion clears the FK, not the snapshots; attribution must
not disappear or be rewritten to the reviewer's later role.

The read-only legacy distinct-value/nullability audit found only canonical
values. Checkpoint 1 leaves legacy review/classification columns, CHECKs and
row values unchanged. A redundant unique `(id, job_id)` key on JobSkill supports
composite ownership FKs without changing data. Strict checks are on new tables
and input contracts. Any future CHECK addition
to legacy columns still requires its own current audit and explicit safe plan.
Never silently coerce existing values. New policy seed canonical JSON/hash is
identical to the pure application constant and immutable in PostgreSQL.

The policy table blocks UPDATE, DELETE and TRUNCATE. Every INSERT checks SHA-256
of exact canonical JSON UTF-8 bytes using PostgreSQL's built-in sha256; no new
hashing extension is installed. V1 must match its fixed canonical bytes/hash,
identity and empty allowlist. Future immutable versions can be inserted with
their own valid identity/hash, not by mutating v1. Checkpoint 2's policy loader
must still call `validate_configuration` after loading a row.

Candidate-owned facts retain ownership cascades. Candidate profile deletion
redacts sensitive snapshots and detaches retained runs using SET NULL,
preserving non-sensitive arithmetic and policy provenance. Source CV or
candidate-fact deletion conservatively redacts that candidate's result,
component, gap and atomic snapshots and marks history unreplayable, including
historical runs. Other candidates/jobs remain unchanged. This privacy erasure
is distinct from ordinary staleness invalidation.
Job deletion/redaction must mark affected history unreplayable and
purge/redact restricted evidence; do not silently leave a replayable snapshot
of deleted content. Preserve non-sensitive historical fingerprints where
permitted, with a nullable job reference if history is retained. Preserve
legacy candidate_job_matches without migration or reinterpretation.

Snapshot only necessary evidence, not complete raw CVs. Source/account deletion
must purge or redact sensitive snapshots and mark affected history unreplayable
where necessary. Immutable history is not permission for unlimited retention.
Policy definitions can remain after personal evidence is removed.

## Invalidation And Historical Reproducibility

| Change | Required Invalidation |
| --- | --- |
| Candidate CV, skill, review, manual evidence or matching fact | Candidate's current runs/results; existing embedding invalidation remains unchanged. |
| Job text/state, skill/review, requirement or fact | Results involving that job; inventory sign-off where its bound inputs changed; shortlist validity where the eligible universe changes. |
| Taxonomy selection, relevant release/content or relationship rule | Dependent results and applicable retrieval inputs. |
| Embedding replacement/staleness, model/template or indexed universe | Dependent retrieval runs and current rankings. |
| Policy activation/version | Current-policy views, without rewriting historical runs. |

Invalidate within the same transaction as relevant writes. Fingerprint-check
on every read; stored invalidation flags are only a cache, never the authority.
GETs never refresh or write. Run creation uses
a consistent input snapshot and rechecks before commit to avoid mixed inputs.

Fingerprint complete reviewed inputs, relevant excluded states, policy,
engine, taxonomy selections/releases/relationship content, and embedding
model/revision/template/source/vector provenance. Embedding rows are upserted,
so row IDs alone are insufficient. Record the retrieved universe and order;
individual-result validity and shortlist validity are different concerns.
Historical results remain explicitly historical, never silently current.
Ordinary job invalidation stales only current runs and their results, leaving
historical rows byte-identical. Policy activation must change current views,
not historical results; Checkpoint 1 has no activation/orchestration API.

When a JobSkill or Q-fact source is deleted, a source-aware database trigger
removes its now-empty parent group and invalidates job inventory/current state.
Surviving multi-member and unrelated groups remain. Direct final-member removal
while its source exists still fails cardinality checks; empty group creation
remains invalid. This covers existing term-replacement/cascade deletion paths
without unconditional empty-group deletion.

## Retrieval-To-Reranking Flow And Permissions

1. Use the supported explicit Template-v2 dense-retrieval path unchanged.
2. Retrieve the matching-policy-v1 primary top-20 pool.
3. Assess approved evidence and readiness for those jobs only.
4. Rerank score-ready results by alignment, original retrieval rank and UUID.
5. Evaluate a candidate's ranking only if the entire top-20 pool is score-ready.
   A UI-only ordering may put scored jobs first and provisional jobs afterward
   in retrieval order; that mixed list is not an evaluated ranking.

The 20-job pool is declared by matching-policy-v1. It corresponds to the Phase 5
Recall@20 reporting cutoff. The frozen Phase 5 ranking contained all 30 jobs.

Reranking within the top 20 does not change any candidate's Recall@20. When
the live top-20 set for each candidate equals the first 20 entries of the
frozen Phase 5 ranking, verified by frozen alias before evaluation, each
candidate's Recall@20 equals its frozen Phase 5 value. The macro average is
5/7 only over all seven grade-2-covered candidates. An average over a subset
reduced by readiness may differ from 5/7 and must not be presented as a
retrieval change or improvement. If the live top-20 set differs from the frozen
prefix, report it as a changed universe and not as the frozen baseline.
Reranking can change ordering measures within the pool, including Precision@K,
MRR@20 and nDCG. The evaluation protocol defines grade-2 MRR@20 once and
requires matched-denominator retrieval-order baselines for every measure.

Missing/stale candidate embeddings produce a readiness error. The repository
excludes stale/missing job embeddings and renumbers returned rows. Therefore
`original_retrieval_rank` means rank after those jobs were excluded, not rank
in a hypothetical complete universe. Make a separate read-only count of
stale/missing eligible jobs and include it in run provenance and readiness
responses. Always warn when the eligible universe is incomplete. No automatic indexing,
lexical fallback or legacy-score fallback is allowed. Report the retrieval-pool
ceiling separately: reranking cannot recover jobs outside the primary pool.
A full-30 corpus diagnostic is exploratory only and cannot replace that pool.

Candidates access only their own evidence/results. Administrator/researcher
roles are additive and may manage policies and job requirements, but do not
automatically authorize arbitrary candidate CV access. Research access needs
explicit consented scope. GETs remain read-only; computation is explicit.

Restricted corpus evidence may be displayed only within the private local
evaluation environment authorized by its terms. Do not publish candidate
evidence, employer text, rationales, UUID mappings or restricted snapshots.
Production candidate views may expose only their own evidence and
public/authorized job evidence.

## Evaluation Methodology And Limitations

See `phase6-evaluation-protocol.md` for the pre-ranking fact-entry freeze,
metric definitions, corpus-specific coverage exception and denominator rules.
Freeze written fact-entry rules before entering benchmark facts. Enter facts,
groups, classifications, criticality, applicability and inventory reviews
without consulting relevance labels, Phase 5 rankings or per-query results.
Freeze the resulting reviewed inputs with a SHA-256 manifest before ranking.
Disclose the owner's prior exposure to aggregate Phase 5 results.

After the first Phase 6 ranking under matching-policy-v1, no fact additions,
edits or removals are permitted for that frozen experiment. Weights/rules are
also frozen before rankings and must not be tuned using the existing judgments.
There is no separate held-out final-matching corpus. Entering frozen-corpus
facts is a controlled data-preparation activity, not application implementation.

Primary metrics require each candidate's entire top-20 pool to be score-ready;
report total/evaluable/excluded candidates and score-ready/provisional job
counts. Do not evaluate a scored/provisional mixture. At least one non-null
end-to-end result is required in automated fixtures and one in declared
demonstration data. An engine returning null for every pair fails acceptance.
This methodology checkpoint creates no ranking, score or metric.

## Four Bounded Implementation Checkpoints

Checkpoints 1 and 2 are implemented as recorded in PROJECT_STATE.md;
Checkpoint 2 is uncommitted for independent review. Checkpoints 3-4 remain
pending. Run creation exists in Checkpoint 2, not the legacy matcher or the
original Checkpoint 1 API surface.

### 1. Policy, Reviewed Facts And Schema

Implement pure deterministic rules, reviewed fact/requirement contracts and
proposed 0009. Likely areas: `app/matching`, models, schemas, repositories,
review APIs and policy documentation.

Acceptance: unit coverage for identities, groups, missingness, applicability,
criticality and caveats; canonical-value rejection, exact arithmetic, identity
conflicts and one-level groups; explicit inventory-complete state/invalidation;
isolated PostgreSQL populated-0008 upgrade, downgrade/re-upgrade, constraints,
deletion and rollback tests; unchanged legacy rows. Manually verify fact-entry
semantics. Audit existing distinct values read-only before proposing new CHECK
constraints on them, with an explicit handling plan. No extraction-based
fabrication of qualification/experience facts.

### 2. Retrieval-To-Result Service

Implement separate runs/components/gaps, the unchanged top-20 retrieval path,
ownership/additive-role authorization and invalidation hooks. Likely areas:
matching service/routes/repository and relevant existing mutation hooks.

Acceptance: deterministic fresh-session persistence, consistent-input checks,
concurrency/rollback with profile locking and current-run uniqueness,
fingerprint checks on every read, stale/missing universe counts, stale refusal,
no write-on-GET, 401/403/404 tests and
unchanged Phase 4 histories/Phase 5 retrieval baseline. Preserve provisional
jobs without assigning them zero. Use isolated PostgreSQL for persistence
claims; do not reuse D033 as general shared-database permission. Require at
least one non-null end-to-end result in automated fixtures.

### 3. Minimal Fact/Inventory Forms And Explanation UI

Provide minimal fact/inventory forms and component, evidence, gap and readiness
presentation in matching API/types, `JobsPage` and `JobMatchPanel`. Include
explicit non_requirement decisions and attributed applicability reason codes.
Full Phase 7 save/dismiss/compare features remain out of scope.

Acceptance: frontend/component checks and production build, full backend and
isolated PostgreSQL suites, manual ownership/evidence/readiness/privacy checks,
and clear UI-only treatment of scored/provisional mixed lists. Explanations
must say candidate-confirmed evidence. No protected/personal-attribute or
eligibility controls. Require at least one non-null result in declared
demonstration data, rather than accepting an all-null system.

### 4. Blind Fact Freeze, Policy Freeze And Corpus Evaluation

Implement only the separately reviewed evaluation tooling and protocol needed
to bind facts, policy, inputs and outputs. Freeze the written fact-entry
protocol before the controlled benchmark-data entry activity; that activity
requires separate authorization and is not an application implementation step.

Acceptance: manifest-bound reviewed facts entered without labels/rankings,
policy freeze before first Phase 6 ranking, no post-ranking fact changes,
complete-pool readiness gates, reported exclusions/denominators, two-run
determinism and independent calculation checks. Reuse existing judgments with
declared limitations. Keep primary top-20 and exploratory full-30 separate;
no new relevance labels, retrospective tuning or skill-gap accuracy claims.

## Accepted D034

The following decision is also recorded in DECISIONS.md. Acceptance does not
claim implementation of its requirements:

> **D034 - Approved-Evidence Explainable Matching Policy v1.** Final alignment
> excludes numeric dense similarity, intentionally departing from the
> MASTER_PLAN draft's 35% semantic component. Similarity remains disclosed
> retrieval evidence and influences ties only through original retrieval order.
> Structured weights are 7:3:2:1 for required skills, preferred skills,
> occupation and qualification/experience. Explicit experience duration/scope
> belongs in Q; other seniority observations are caveats only. Only approved
> evidence contributes, described as candidate-confirmed rather than
> independently verified. Canonical classifications are required, preferred,
> non_requirement and unknown. Complete scoring requires resolved attributed
> applicability, explicit current reviewed inventory completeness, at least one
> approved required/preferred skill group and full applicable assessment.
> Pending bound rows or approved unknown classifications block sign-off;
> qualifications/experience require Q groups or explicit non_requirement review.
> Unavailable assessments produce provisional results, not invented zeros/full
> credit. Identity and conservative text-only rules cannot override conflicting
> concepts or bridge releases/systems. One-level groups use declared unknown
> propagation and deduplicated members. Relationship allowlist must equal [].
> Critical deduction uses maximum missing support among reviewed critical
> required groups, zero if none; unknown critical support prevents a complete
> score. Exact rational scores determine ordering. Separate relational runs
> preserve legacy matches; every read verifies fingerprints. The top-20 pool is
> declared by this policy, not the frozen Phase 5 pool. Primary evaluation
> requires the entire pool to be score-ready. Fact-entry protocol, reviewed
> facts and policy are frozen before rankings, with no post-ranking fact edits.
> Reused judgments are never tuning input or independent held-out validation.

> Decision clarifications: full identity support requires exact same-release
> concept identity or the declared conservative text-only rules. Exact-score
> ties use retrieval rank, then lowercase canonical job UUID. Explanations are
> advisory and evidence-bound. There is no eligibility or protected/personal-
> characteristic component or input. Policies and separate runs are immutable
> and versioned; substantive policy changes require a new immutable version.
> Legacy candidate_job_matches are preserved, not reinterpreted. The Phase 5
> retrieval baseline remains frozen under D032.

Corpus-specific coverage counts and denominator policy are documented in the
separate evaluation protocol, not embedded in this general matching decision.

## Reviewed-Input API Surface (Checkpoint 1)

All routes are under `/matching-inputs` and require authentication:

- GET/POST `/candidates/{profile_id}/facts`; DELETE the owned fact by ID.
  Candidate role and owner match are required; foreign profiles return 404.
  No new administrator/researcher access to arbitrary candidate facts exists.
- GET `/jobs/{job_id}/inventory` returns current inputs and their recomputed
  fingerprint, plus whether an existing sign-off remains current.
- POST/DELETE job facts and requirement groups; PUT occurrence classifications
  and inventory sign-off. Job management requires admin or researcher, including
  accounts also carrying candidate. Ordinary candidates receive 403.

Every mutation requires `expected_fingerprint`. Writes lock the owning job or
candidate profile, reject stale fingerprints, and commit reviewed-input and
current-run invalidation together. GETs only read; no get-or-create behavior.
Repeated unchanged classification/sign-off is a no-op. Reviewed facts/groups
are created and explicitly deleted/recreated for corrections; no unrestricted
update of immutable per-review attribution is offered. Schemas forbid extra
fields, including protected-characteristic inputs. The APIs do not index,
score, retrieve, change Phase 4 decisions or alter legacy matches/embeddings.

Candidate fact creation/replacement requires an active owned profile. Missing
profiles return 404; inactive/deleted retained profiles cannot create facts.
Deletion remains available for privacy. Existing manual candidate-skill review
has no profile-level CV-processing-consent prerequisite; the existing consent
flag gates CV processing and dense retrieval/indexing. This checkpoint adds no
new consent model for explicit candidate-confirmed manual facts and does not
infer permission from unrelated fields. Referenced CV ownership is still checked.

## Remaining Prerequisites

Independent review has accepted the methodology. Complete scores require
explicit reviewed inventories and
applicable occupation, qualification and experience facts that current keyword
extraction cannot safely establish. Until those inputs exist, return transparent
provisional assessments. Existing values must not be silently reclassified or
historical developer data repaired as part of implementation.

Checkpoint 2 adapts approved reviewed inputs to the unchanged pure engine and
persists owned runs/components/gaps. POST `/matching-runs` is the only computation
entry point, with no pool/model/policy overrides. GET by run ID and GET current
only read and verify fingerprints; the latter can disclose the latest stale
attempt without refreshing it. Missing/stale candidate indexes return 409.
Unauthorized requests return 401/403; foreign-owned results return 404.

Migration 0010 adds immutable-run provenance fields and component ratio checks.
It also serializes source mutation/run creation through advisory lock 603402
and the candidate row lock. Source writes invalidate only current runs/results
in the same transaction; universe/taxonomy changes conservatively invalidate
all current runs. Identical source updates do not stale history. Every read
rebuilds input hashes (without retrieval or encoding vectors); flags are only a cache.
Hash-only provenance is bounded to 256 KiB and contains selected-pool metadata
plus the entire universe's fingerprint, not source documents. Sensitive evidence
snapshots remain on results/components/gaps under the existing erasure triggers.

Reviewer pseudonym handling requires no change: the internal random reviewer
ID is hashed, not replaced with a personal name/email. Snapshots preserve the
role at review time and survive reviewer FK deletion. Q phrase extraction alone
cannot establish a qualification/experience assessment; structured reviewed
facts are required. Unsupported equivalences or occupation incompatibility
claims abstain as unknown, not invented zero support. Skill unknowns remain
visible and unscored. Exact fractions, selected taxonomy provenance and all
compared evidence references survive arithmetic deduplication.

No facts have been entered for the frozen corpus and no real-data scores or
evaluation have been produced. No frontend, fact freeze, deployment or model
execution is included. Phase 6 remains incomplete.
