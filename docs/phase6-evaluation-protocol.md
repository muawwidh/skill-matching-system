# Phase 6 Evaluation Protocol

Status: **ACCEPTED METHODOLOGY** on 2026-11-10 after independent review.

This is the accepted evaluation protocol for `matching-policy-v1`, accompanying
`phase6-explainable-matching.md`. It does not authorize data entry, ranking,
metrics, database access or changes to frozen Phase 5 evidence. No Phase 6
evaluation has been performed by writing this document.

Acceptance freezes this protocol and `matching-policy-v1` methodology before
implementation and before Phase 6 rankings. Checkpoint 1 now implements the
pure policy engine and reviewed-input APIs/models with migration 0009, verified
in isolated PostgreSQL only. This does not create benchmark facts, a fact freeze,
rankings, production scores or evaluation results. Checkpoint 2 now implements
the owned explicit-run service, unchanged top-20 retrieval, persistence and
readiness/currentness checks, verified only with synthetic isolated fixtures.
New migration 0010 is not applied to the developer database by this work.
The earlier separately authorized developer migration to 0009 is not benchmark
fact entry or evaluation. Next is Checkpoint 3's minimal forms/explanation UI;
this protocol and matching-policy-v1 remain unchanged.

## Acceptance History

Accepted pre-promotion protocol SHA-256:
`33f97280dca56a9d8d15f861facfc7e515a748534dcc815a778131aa1557c3fc`.
Accepted pre-promotion matching-policy document SHA-256:
`3c453b660d80c7f1521a26548737048c58c00dcb3825f9ab994383551e4a5d8c`.
Promotion records acceptance on 2026-11-10 without changing the reviewed
methodology. The matching-policy document preserves the earlier proposal
revision history.

## Baseline And Experiment Scope

- Branch: `phase6-explainable-matching`.
- Repository/Phase 5 checkpoint: `349e668f670f71dadfa7d4680fdcb1ceef334321`.
- Reuse the frozen eight-candidate, thirty-job corpus and all 240 human
  judgments without changing labels or requesting another 240-pair review.
- Existing grades are 167 grade 0, 54 grade 1 and 19 grade 2.
- The corpus is curated, restricted internal material, not a representative
  sample of hiring outcomes. Profiles were manually reviewed/augmented.
- There is one rater and no inter-rater reliability estimate. There is no
  separate held-out final-matching corpus.

The project owner previously saw aggregate Phase 5 results. Disclose that
exposure and reuse of the corpus; do not describe Phase 6 as independent blind
held-out validation. No weights, rules, fact decisions or representation changes
may be chosen using relevance labels or per-query Phase 5 outcomes.

## Mandatory Pre-Ranking Preparation Freeze

Entering frozen-corpus facts is a separately authorized, controlled
data-preparation activity, not application implementation. Before any Phase 6
ranking, perform the following in order:

1. Freeze a written fact-entry protocol defining source interpretation,
   alternatives, grouping, classifications, criticality, qualification
   completion, experience duration/scope, applicability and inventory review.
   Preserve source caveats and define unknown rather than inventing facts.
2. Enter requirement groups/operators, canonical classifications, reviewed
   criticality, applicability decisions, inventory reviews and candidate facts
   without consulting relevance labels, Phase 5 rankings or per-query results.
   No candidate/job family alignment or expected matches guides entry.
3. Validate accounting of bound occurrences: no pending bound rows, no
   approved unknown classifications, and qualification/experience occurrences
   in Q groups or explicitly reviewed non_requirement. No-pending rows alone
   never establish completeness; require explicit job-level sign-off.
4. Record attributed applicability decisions and inventory fingerprints.
   Freeze all reviewed inputs, the written protocol and canonical policy with
   SHA-256 manifests, source bindings and timestamps before rankings exist.
5. Generate rankings only after the freeze is independently checkable. After
   the first Phase 6 ranking under matching-policy-v1, prohibit fact additions,
   edits and removals for that experiment. Do not tune rules or weights using
   the existing judgments. A discovered defect requires stopping and recording
   the problem, not silently changing the frozen experiment.

Record the protocol, reviewed-input and policy hashes in every run/evaluation.
Use dedicated isolated benchmark storage for future reproductions; the
run-specific Phase 5 D033 exception is not general shared-database permission.

## Primary Retrieval Pool And Readiness

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
MRR@20 and nDCG.

Use unchanged Template v2 and the pinned model/revision. Report retrieval-pool
coverage separately from ordering. Do not widen the primary pool after seeing
results. A full-30 reranking diagnostic is exploratory and never replaces the
top-20 policy pipeline or its reported results.

The repository excludes stale/missing job embeddings and renumbers results.
`original_retrieval_rank` therefore means rank after those exclusions. Make a
separate read-only count of stale/missing eligible jobs, bind it into run
provenance/readiness, and warn whenever the eligible universe is incomplete.
Do not silently describe a changed/incomplete universe as the frozen baseline.

A candidate is score-ready for primary ranking evaluation only when its entire
declared twenty-job pool exists and every job has a non-null, current complete
score. Any provisional/unscorable job excludes that candidate from primary
ranking metrics; fewer than twenty retrieved jobs cannot constitute a complete
pool. Missing/stale candidate embeddings prevent evaluation as well.

Always report total candidates, score-ready candidates, evaluable candidates,
excluded candidates with reasons, score-ready job counts and provisional job
counts per candidate and overall. Report score-readiness exclusions separately
from relevance-coverage exclusions and show their intersection for each metric.
No excluded candidate receives an artificial zero.

Do not evaluate a list mixing scored and provisional jobs. A UI-only ordering
may show scored jobs first and provisional jobs afterward in retrieval order;
it is not an evaluated ranking and must be labelled accordingly.

## Predeclared Metric Sets

### Grade-2 MRR@20 Definition

For a grade-2-covered candidate with a score-ready twenty-job pool, RR@20 is
the reciprocal of the first grade-2 rank in that list, or zero if no grade-2
job appears in the twenty entries. MRR@20 is the macro mean of those RR@20
values over the explicitly reported evaluable candidates. A candidate with no
corpus grade-2 judgment has undefined RR@20 and is excluded, never assigned
zero. All later MRR@20 references use this definition.

MRR@20 is not comparable with the frozen Phase 5 MRR of 1261/1925, which used
the full ranking. For every primary and diagnostic measure, also report a
predeclared retrieval-order baseline. It applies the same metric to the frozen
Phase 5 top-20 order, over exactly the same evaluable candidates and denominator.
The baseline is a derived diagnostic. It does not alter or replace any Phase 5
result. If a separately labelled full-30 exploratory measure is reported, its
retrieval-order comparator uses the corresponding frozen full-30 order and the
same declared cutoff and denominator, never a mismatched top-20 comparison.

### Primary Reranking

Pool: top 20, with complete-pool score readiness mandatory.

- Precision@5 and Precision@10: grade 2 is relevant; numerator is the number
  of grade-2 jobs in the first K positions, denominator K.
- MRR@20: use the Grade-2 MRR@20 Definition above.
- nDCG@5, nDCG@10 and nDCG@20: linear gain equals the relevance grade 0/1/2,
  not exponential gain. `DCG@K = sum(grade(rank)/log2(rank+1))`. IDCG uses the
  best K grades from the full frozen thirty-job judgment set, so retrieval
  omissions are not hidden by a pool-only ideal. Zero IDCG means undefined.

Macro-average per-candidate values over each metric's explicitly reported
evaluable denominator. Binary primary metrics retain the accepted grade-2
coverage exception; graded nDCG may include any score-ready candidate with
positive IDCG. Do not conceal different denominators in one unlabeled average.
No candidate with an unready pool enters any primary aggregate.

### Binary Diagnostic

Grade 2 alone is relevant. Report Recall@5, Recall@10, Recall@20 and MRR@20 for
the same primary pool with explicit readiness gates. Recall denominator is
the candidate's total grade-2 jobs in the full thirty-job corpus, not only
those retrieved. Grade 0 and grade 1 are not binary relevance. MRR@20 uses the
single Grade-2 MRR@20 Definition above, not a separate diagnostic definition.

The accepted corpus-coverage policy has eight total queries, seven with
grade-2 relevance and one excluded/undefined query,
`candidate_831967b28fd6`. Its binary Recall and MRR@20 remain null, not zero; do not
promote grade 1. The existing coverage is 7/8 and its coverage-based binary
denominator is seven. Readiness can reduce the actual evaluated denominator
further: use the intersection of those seven with score-ready candidates and
report both denominators and every exclusion explicitly. Do not force a
seven-query mean if some pools are unready.

This coverage exception was adopted after the relevance judgments were
collected. Preserve the accepted policy and exact label/export bindings; do
not infer new exclusions from ranking performance.

### Graded Diagnostic

Use grades 0/1/2 for separately labelled exploratory/descriptive analysis of
all eight candidates where mathematically defined. The candidate without
grade-2 relevance is retained here when its graded ideal is nonzero. Report
readiness, definitions and denominators; do not substitute graded diagnostics
for primary binary relevance or silently treat uncertainty as grade zero.
Linear-gain nDCG is the predeclared graded ordering measure; no additional
metric is introduced opportunistically after seeing rankings.

Phase 5 retrieval metrics, rankings and artifacts remain unchanged. The
Phase 6 primary/diagnostic distinction is not a replacement interpretation of
that frozen evaluation.

## Integrity, Acceptance And Reporting

Bind candidate/job IDs privately to aliases, reviewed source/input hashes,
policy/engine version, retrieval model/revision/template, pool/order and the
existing judgment/corpus policy hashes. Keep labels unavailable to fact entry
and ranking generation; load them only for the separately authorized evaluation.

Require repeatable ranking and evaluation artifacts with manifests and
independent arithmetic checks. Preserve exact fraction score ordering before
Decimal display rounding. Keep all exclusions visible rather than imputing
scores or metrics. Do not create prototype-match rows as evaluation storage.

Acceptance requires at least one non-null end-to-end result in automated
fixtures and at least one in declared demonstration data. An all-null system
fails Phase 6 acceptance. These minimum checks do not waive the complete-pool
gate for primary metrics; if no candidate has a score-ready pool, report no
primary aggregate rather than claiming successful ranking evaluation.

Relevance labels do not establish skill-gap ground truth. Test explanation
reconstruction, evidence support, deterministic gaps and abstention mechanically;
do not claim skill-gap accuracy/F1 without separate appropriate reference data.
Do not claim calibrated hiring accuracy, independent held-out validation or
end-to-end extraction quality. No new relevance labels are required or created.

Restricted candidate/job evidence may be displayed only inside the private
local evaluation environment permitted by the corpus terms. Do not publish
candidate evidence, employer text, rationales, UUID mappings or restricted
snapshots. Public reporting may contain permitted aliases, hashes, aggregate
metrics and limitations. Production candidate views may show only their own
evidence and public/authorized job evidence.

## Implementation Boundary

The four implementation checkpoints are defined in the accepted matching policy:
policy/schema/review APIs; retrieval/persistence/currentness; minimal forms and
explanation UI; then separately controlled fact/policy freezes and evaluation.
This is an accepted methodology/design checkpoint under D034, not an
completed Phase 6 evaluation. Checkpoint 1's application foundation does not
authorize or perform benchmark fact entry, rankings or evaluation. Migration
0009 exists and was applied in a separate authorized operational task; this
checkpoint never accesses the developer database or applies new migration 0010. Reviewed corpus
fact/inventory entry and all evaluation execution remain separately controlled
future work; judgments and frozen evidence remain unchanged.
