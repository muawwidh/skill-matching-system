# Phase 6 Fact-Entry Protocol

Status: **DRAFT FOR OWNER REVIEW**, prepared 2026-11-14 against cb0c8e7.
Protocol identity: `phase6-fact-entry-v1` (not yet frozen).

This operational draft implements the preparation requirements of
[the accepted evaluation protocol](phase6-evaluation-protocol.md) and
[matching-policy-v1 / D034](phase6-explainable-matching.md). It does not change
scoring, identity, readiness, metrics or policy. No corpus facts, preview rows,
benchmark database, embeddings, runs or evaluation are created by this document.
No prior standalone fact-entry protocol was found in tracked docs or the private
local area; the accepted evaluation protocol remains authoritative.

## Approval And Information Barrier

Owner approval and a recorded SHA-256 of this written protocol must precede
corpus fact entry. A later input manifest binds that exact approved revision.
Authorization to prepare this draft is not execution authorization.

The owner authored all 240 Phase 5 relevance judgments and has seen aggregate
Phase 5 results. Explicitly disclose both exposures in preparation and experiment
provenance. Record any other prior exposure by each operator without claiming
prior knowledge can be erased. The information barrier means no consultation
during preparation; it does not establish historical blinding or independent
held-out validation.

During source interpretation and fact entry, do not open relevance labels,
rationales, excluded-query policy, ranking/score exports or per-query results.
Do not use expected candidate/job families, anticipated matches or candidate
availability to decide a job requirement. Interpret candidates independently
of jobs and jobs independently of candidates. Do not invent model-generated
facts, source claims, equivalences or explanations. Source-bound agent/tool
drafting and schema-valid payload proposals are permitted within this barrier:
transcribing a cited source assertion, retaining its caveats and proposing its
structure is not evidence generation. An assertion absent from the source or
strengthened beyond it is invented and prohibited. Do not request new relevance
judgments or tune weights/rules.

Use an explicit source-file allowlist: frozen sanitized candidate evidence,
frozen reviewed candidate skill state, normalized job sources and their accepted
reviewed occurrence state, private ID mappings, source hashes and selected
taxonomy definitions needed for identity. Verify provenance through an
allowlisted hash inventory; do not load a mixed result/label-bearing record to
obtain otherwise available source metadata. If a file combines permitted source
information with prohibited outcomes, obtain a separately authorized source-only
view, not a full copy. Keep interpretation records private.

## Access Authorization And Attribution

Before execution, identify the governing corpus terms and consent/permission
evidence, including their versions or hashes and the permitted purposes/actions.
Internal testing approval is not automatically permission for delegated account
use. Require a separate explicit authorization record naming the actual human
operator, reviewer and their roles, covered candidate/job entities, permitted
delegated actions, applicable account scope and the governing evidence. If this
scope is absent or insufficient, stop. Do not invent, infer or assume consent.
Possession of candidate credentials is not authorization to impersonate a person.

Corpus facts are to be researcher-transcribed from approved source evidence;
they are not newly confirmed by the actual candidate/CV author. Existing
candidate-fact APIs require the candidate role and ownership of the target
profile. Researcher/admin roles alone cannot write another candidate's facts.
This document neither bypasses that restriction nor adds a delegated-entry API.
If no properly authorized human entry route exists, stop for an explicit access/
implementation decision rather than substituting credentials or direct SQL.

Under the current candidate-owned API, the server records the authenticated
account as `reviewed_by`, derives its reviewer pseudonym and role snapshots from
that account, and sets `provenance=candidate_confirmed`. Those fields cannot
identify a distinct researcher operating under delegation or prove a new
confirmation by the actual candidate. Keep the actual human operator and reviewer in the private
ledger separately from the authenticated account and returned server attribution.
Do not overwrite attribution or imply those identities are interchangeable.

Public methodology must disclose that evaluation facts are researcher-transcribed
source assertions, not new candidate confirmations, and that the server's
candidate-owned attribution/provenance cannot independently distinguish that
delegation. Preserve the policy/API term candidate-confirmed where required, but
explain this evaluation attribution limitation; do not publish private identities,
account mappings or credentials. No corpus facts have been entered yet.

## Agent Drafts And Human Approval

Record agent/tool identity, version where available, drafting time and output
hash separately from human operator/reviewer identity, role, review time and
decision. Agent drafts and proposed API status values are not approvals, even
when a schema-valid preview proposes `review_status=approved`.

A named human must review every proposed fact, classification, group/operator,
criticality, applicability and completeness decision against its cited source.
A consolidated review packet is permitted: record the disposition of each
identified proposal, source corrections, reviewer and time. Do not require
repetitive UI entry as proof of review, or treat an unreviewed row as approved
because the packet was opened. Retain the approved packet hash in the input
freeze and bind returned API IDs to the individually reviewed decisions.

Agents must not authenticate as candidate accounts or submit approved-status
writes or inventory sign-offs under this protocol. Application writes require
the authorized human operator and supported APIs; a consolidated approval packet
does not bypass authorization, ownership or server readiness. This draft grants
no agent execution authority and creates no new batch/import endpoint.

## Source Accounting Before Database Entry

First perform a separately authorized source-only representability audit, without
creating a database, entering facts or calculating pair supports/scores. Validate
logical expressibility and API schemas, not candidate-to-job fit. This audit is
not yet performed and does not promise a score-ready corpus.

For every proposed fact, occurrence classification, group and applicability
decision, plan a private ledger entry with:

- source entity alias and immutable source SHA-256;
- exact supporting sentence/contiguous span, line/section and character range
  in the identified source; no splice of non-contiguous fragments;
- intended field values, retained caveats, source-to-structure rationale and
  any omitted/out-of-scope/unsupported material;
- draft origin (agent/tool, version/time/hash) separately from the actual named
  human operator/reviewer (or controlled ID resolving to that named human),
  their roles, per-decision approval and review time;
- governing terms/consent evidence and explicit authorization-record binding,
  protocol version and the input/source fingerprint to which review is bound;
- later, the actual returned fact/group/member/occurrence-review IDs and
  server-recorded attribution, not guessed IDs or fabricated review dates.

The ledger is not created here. Its evidence and private mappings must never
enter tracked docs. Public reporting may use permitted hashes/counts/limitations.
Do not retain candidate/job protected or irrelevant personal attribute values
in matching inputs or the ledger; record only their exclusion category where
accounting is needed. Minimum private reviewer-accountability metadata is
separate from matching evidence and must not be published as a personal identity.

Read the complete source, not only extraction output. Missing extracted rows
do not establish no requirement, no occupation scope or inventory completeness.
Record a source requirement even if no API can encode it. Never silently omit
it to achieve sign-off or an evaluable denominator.

## Source-Bound Candidate Inputs

Preserve the frozen approved/rejected skill collection and qualification caveats.
Do not resubmit replacement collections, add benchmark skills, reprocess CVs,
relink taxonomy or alter Phase 5 input text under this protocol.

Propose only occupation, qualification or experience matching facts directly
established by the authorized sanitized source. These corpus additions are
researcher transcriptions, not new confirmations by the actual candidate and not
independently verified credentials. Human-reviewed entry is conditional on the
governing terms/evidence and explicit delegation scope above. Candidate-owned
server attribution and actual researcher/operator attribution remain distinct;
neither researcher role nor credential possession bypasses ownership.

- Preserve an unfinished/unconfirmed qualification as `in_progress`,
  `not_completed` or `unknown`, according to the source. Institution attendance
  alone does not prove completion. Do not copy job wording into a candidate
  fact to manufacture an exact qualification match.
- Retain field, experience scope, supervision, reported-use and duration caveats.
  Do not infer proficiency, independent practice, occupation equivalence or
  standalone seniority. Interests are not evidence of ability.
- Store exact explicit durations only. Whole years may be mechanically converted
  to months (years x 12), with the original unit and conversion recorded.
  Do not sum overlapping jobs, infer full-time equivalence or convert uncertain
  dates/ranges into an invented exact duration. Unrepresentable bounds stay
  documented and unknown for unsupported comparisons.
- A named human may approve a fact only when the assertion is source-supported.
  An approved assertion may contain unknown completion/duration and remain unassessable.
  Review status is not a substitute for missing factual knowledge. Leave genuine
  interpretation disputes pending; rejected claims never become scoring evidence.

## Job Inventory And Classification

Account for all occupational requirements and duties, qualifications/experience,
and explicit alternatives in the complete normalized posting. Preserve source
distinctions: `required`, `preferred`, `non_requirement`, `unknown`. The latter
two are not convenient substitutes for difficult requirements.
Do not edit job/source text or reprocess jobs to manufacture missing skill rows.
Missing supported capabilities remain representability blockers, not permission
to alter the frozen extraction input or repurpose an unrelated occurrence.

An existing extraction occurrence may be reviewed `non_requirement` for true
noise, unsupported text or a documented redundant projection. For a redundant
qualification/experience extraction, retain the complete real requirement in
approved structured Q facts/groups and bind the duplicate-review reason to
those sources in the ledger. Do not classify a real requirement out of scoring
merely because it is inconvenient or unsupported. No duplicate may inflate
arithmetic credit.

An override of legacy `requirement_type` requires the occurrence-review API's
explicit classification, approved review, source-bound reason and current
fingerprint. The legacy skill and the Phase 6 classification are distinct;
do not modify the frozen extraction review just to make groups acceptable.

### Groups And Alternatives

- R groups use required occupational capabilities; P groups use preferred
  capabilities. Qualifications/experience belong in Q, never R/P.
- `SINGLE` has one atomic member; `OR` preserves explicit alternatives; `AND`
  preserves explicitly combined members. Do not turn examples into mandatory
  conjunctions. A mixed/ambiguous clause remains unresolved.
- Each job skill occurrence or reviewed Q fact belongs to at most one group.
  Keep all source references while deduplicating identities as the engine does.
- Only one-level groups are supported. Conditional routes such as an OR of
  degree-and-duration combinations, nested groups and cross-component
  alternatives must not be flattened into a different logical requirement.
  Unsupported structure is a stop/blocker, not permission to approximate it.
- Reviewed Q facts need explicit statement/completion/duration/field/scope as
  applicable. Putting an extracted phrase in a Q group alone does not make
  it assessable: the adapter reports `explicit_q_fact_required`.

For this proposed entry protocol, criticality defaults to false. Ordinary
required wording, section order or reviewer expectations do not automatically
make a group critical. A critical
flag requires an explicitly reviewed approved R group and a source-bound
rationale identifying why that capability is explicitly critical/non-negotiable;
retain the rationale in the private ledger because GroupInput has no free-text
reason field. Do not set criticality based on candidate gaps or outcomes.
The accepted maximum critical deduction is unchanged.

### O/Q Applicability And Completeness

`not_applicable` requires actual source review, the fixed reason code, reviewer
pseudonym/role snapshot, timestamp and current inventory fingerprint:

- O: `no_occupation_scope_stated`;
- Q: `no_qualification_or_experience_scope_stated`.

Use these only when the source genuinely has no such scope. Missing structured
rows, a missing taxonomy link or a difficult degree/experience comparison do
not justify not_applicable. Undecided applicability is `unknown`.

Do not sign inventory complete while any bound occurrence is pending, any
approved occurrence is classified unknown, a qualification/experience occurrence
has neither Q accounting nor legitimate explicit non_requirement review, groups
or facts are stale/unreviewed, O/Q applicability is unresolved, or a source
requirement remains unrepresented. Server acceptance alone cannot prove semantic
source completeness. Require ledger reconciliation and explicit reviewer sign-off.
No-pending rows alone never prove completeness.

Use current `expected_fingerprint` values on writes. On conflict, stop, reload
and reconcile deliberately; never replay a successful create blindly. Before
the experiment freezes, the existing fact/group correction contract is explicit
delete/recreate, not an invented update endpoint. Preserve the change log and
returned IDs. Do not repair sources, taxonomy or embeddings as a side effect.

## Current API Representability Gate

This is a code/contract assessment, not an audit of the thirty actual postings.
Storing prose and assessing its meaning are different capabilities.

| Evidence | Existing support | Limit that must not be disguised |
| --- | --- | --- |
| Candidate occupation/qualification/experience | Owned fact POST; source/CV reference and explicit structured fields | Researcher transcription is not new subject confirmation; server attribution follows the candidate-owned account, not a separate delegate. Explicit access authority and separate human ledger attribution are required; candidate skills remain frozen. |
| Job occupation/qualification/experience | Manager fact POST and Q groups | Only these three fact types; an occupational skill cannot be invented as a job fact. |
| Required/preferred capability | Groups referencing existing approved JobSkill rows | No supported manual job-skill creation endpoint. A missed source capability can block true completeness even when the server has no row for it. |
| Extracted qualification/experience phrase | May be accounted for in Q or explicitly reviewed as a real duplicate/non_requirement | Phrase-only Q support stays unknown; do not mistake text review for structured fact assessment. |
| Alternatives | Flat SINGLE/OR/AND over allowed atomic references | No nested/conditional/cross-component logic; no O-group OR contract. |
| Qualification comparison | Normalized statement identity, matching nonempty field/scope and explicit completion; no qualification duration | Different wording/degree hierarchy/equivalence is unknown. Do not harmonize assertions solely to force a match. |
| Experience comparison | Matching explicit field/scope, supported completion and integer month comparison | No period aggregation or inferred experience scope; missing or incompatible facts abstain. |
| Occupation comparison | Same reviewed concept in a selected taxonomy release | Different/unlinked occupations are unknown, not proven incompatible; title/industry alone is not full identity. |
| Applicability and inventory | Explicit attributed reviews bound to current fingerprints | Passing a schema or having no pending rows is not proof all source requirements were represented. |

API fields have limits (statement 1000 characters, evidence reference 255,
field 255, scope 500; groups at most 100 members). Use a compact immutable source
reference where appropriate, not a silent truncation that drops meaning.
Taxonomy identity on facts is occupation-only and requires both concept/release
IDs. Use existing reviewed release identities, not a taxonomy import/relinking
campaign or new aliases designed for the benchmark. Relationships stay disabled.

Relevant implementation: `app/schemas/matching_inputs.py`,
`app/api/routes/matching_inputs.py`, `app/services/matching_inputs_service.py`,
`app/matching/assessment.py` and `app/matching/policy.py`. Routes under
`/matching-inputs` provide owned candidate facts; manager job facts, groups,
occurrence classification and inventory reviews. They do not provide new
manual job skills or unrestricted candidate management.

Conclusion: the APIs can represent a conservative subset faithfully, not every
possible posting or comparison. No whole-corpus sufficiency claim is justified
yet. If the source-only audit finds an essential unrepresentable requirement,
pause for a separately authorized implementation-scope decision, or keep the
affected inventory incomplete and disclose resulting non-evaluability. Do not
omit requirements, mark O/Q not_applicable, alter the corpus, coerce fields or
weaken readiness just to obtain scores. No scoring-policy choice is reopened.
Unknown factual knowledge is not an invented zero. This does not change the
accepted R/P `not_evidenced`/Missing rule or identity-incomparable zero support;
those are policy-defined skill comparisons, not permission to invent negative
qualification/experience facts or occupation incompatibility.

## Input Freeze And Subsequent Execution Gates

After protocol approval and a defensible source-only audit, execution still
requires separate authorization for an isolated benchmark environment and
source-bound human-reviewed entry, with governing terms/consent evidence and
the explicit operator/entity/action authorization record. Reuse the frozen
corpus/labels and reviewed evidence without altering historical Phase 5 files.
Candidate/job source interpretation is independent; no new pair labels or
expected-match annotations are created.

Before the first Phase 6 ranking, freeze the reviewed inputs and canonical
matching-policy-v1 configuration with a SHA-256 manifest. Include protocol,
source hashes, reviewed facts/groups/members/classifications/applicability,
inventory fingerprints, separate draft/human/server attribution and authorization
bindings, selected taxonomy, private entity bindings, code/model/template
versions and declared experiment identity.
Review and approve the manifest before authorized indexing/run creation.
Do not create preliminary runs to decide which facts to add or remove.

After the first Phase 6 ranking, no additions, edits or removals of facts,
groups, classifications, criticality or applicability are allowed under that
experiment identity. No rule/weight/model/template tuning using judgments.
Any post-ranking input correction requires stopping and a separately approved
new experiment identity, retaining the original freeze and results. A policy
change additionally requires a new immutable policy version; an input correction
does not itself change matching-policy-v1. Never quietly change the baseline.

The accepted evaluation protocol alone controls metrics: complete score-ready
top-20 pools, explicit exclusions/denominators, matched retrieval-order baselines,
the preserved grade-2 coverage exception, and separated diagnostics. Null is not
zero. Do not evaluate scored/provisional mixtures. If no full pool is ready,
report no primary aggregate, not a successful reranking evaluation. This draft
does not perform readiness scoring, indexing, ranking or metric calculation.

## Owner Gates And Smallest Execution Sequence

1. Approve and hash-freeze these entry rules, governing terms/consent evidence,
   explicit named operator/reviewer, covered entities and permitted delegated
   actions, and prior-exposure declaration; finish the outstanding manual
   ownership/privacy and accessibility acceptance separately.
2. Authorize only the source-only representability/coverage audit and agent/tool
   draft proposals first. Produce a private source ledger and schema-valid plan
   without pairing/scoring, using the information barrier. Report missing API
   contracts before provisioning. Draft origin is not human approval.
3. If defensible, obtain named human review of each decision (a consolidated
   packet is sufficient) and authorize isolated setup and human-operated entry.
   Agents do not authenticate as candidates or submit approved writes/sign-offs.
   If not defensible, decide whether to pause for a minimal separately reviewed contract implementation
   or accept explicitly incomplete inventories/non-evaluable queries. Neither
   path permits invented facts, policy relaxation or a post-result change.
4. Reconcile sources and reviews, freeze the complete input/policy manifest,
   then separately authorize pinned indexing, top-20 runs and the already
   accepted deterministic/baseline-controlled evaluation. No execution begins
   merely because this draft exists.

No additional relevance review, weight choice or expansion of the primary pool
is requested. Single-rater, prior-exposure, reused-corpus and coverage limitations
remain those of the accepted evaluation protocol.

## Existing Demonstration Evidence

The completed synthetic ready/provisional display inspection is separate from
corpus entry and the remaining ownership/privacy/accessibility acceptance.
Its private acceptance record was verified at SHA-256
`32c4651a58a97ff51a8c07e5a508cb241bb5fb705d1ad0b59e98b87599629ec8`.
This reference publishes neither its private path nor credentials and does not
claim the owner tested input saving, stale transitions, permissions or duplicate
submissions.
