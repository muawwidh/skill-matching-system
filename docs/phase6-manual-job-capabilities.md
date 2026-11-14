# Source-Bound Manual Job Capabilities

Status: **ACCEPTED** by the project owner on 2026-11-14. Design approval only.
Baseline: `a8a9685`, branch `phase6-explainable-matching`.

## Revision History

- 2026-11-14: Materialized the chat-only proposal and incorporated independent
  review corrections for deletion, fingerprints, duplicate protection, review
  states, coordinates and database integrity. The final reviewed draft adopted
  option (a) for pending/rejected extracted-key conflicts and clarified criticality
  and history/downgrade regression requirements.
- 2026-11-14: Owner accepted the reviewed design under D035. Pre-promotion
  SHA-256: `d184103eaf2523fa3b9cf62e37b0e3993266c1f4884d8a1ec37fc2da234fdc94`.
  Promotion changes status only, not the extension contract. Implementation,
  migration execution, deployment and corpus entry require separate authorization;
  none is performed or authorized by this acceptance. Frontend work remains deferred.

This materializes and corrects the earlier chat-only extension proposal. No
extension design file previously existed. It supersedes that proposal's
capability-deletion erasure behavior, permissive review states and deferred
duplicate rules. It does not authorize implementation, migration, entry,
provisioning or execution. D034, matching-policy-v1 and the accepted
[evaluation](phase6-evaluation-protocol.md) and
[fact-entry](phase6-fact-entry-protocol.md) controls remain unchanged.

## Boundary And Storage Choice

Do not insert manual capabilities into JobSkill or ExtractedJobTerm. The
retrieval repository reads all JobSkill rows: an added row changes the v1/v2
source hash even if rejected; an included row can also change representation
text. A stored ready embedding then fails currentness independently of its flag.
Normal skill mutation workflows can additionally stale embeddings.

Use a separate `job_manual_capabilities` table, excluded from Phase 5 retrieval
builders, source hashes, embedding invalidation and legacy prototype matching.
Never update the jobs row, including updated_at, when capabilities are created
or deleted. Do not change frozen extraction rows/reviews or source text, edit/
reprocess jobs to manufacture skill rows, relink taxonomy or rewrite artifacts.

The extension supplies additional reviewed R/P evidence to the existing policy,
not a different scoring formula. It must not introduce nested, conditional,
threshold, equivalence, eligibility or proficiency rules. It does not guarantee
evaluable top-20 pools; Q/O, source completeness and alternative-route limitations
remain independent blockers.

## Human Workflow And Minimal API

Require the existing admin/researcher manager dependency, actual authorized human
operation and governing corpus/entity/action authorization. Candidate role alone
has no write access. No candidate-account impersonation is needed. Agents may
prepare cited drafts/schema-valid proposals but may neither authenticate as
candidates nor submit approved-status writes/sign-offs under the entry protocol.

Defer frontend selection and form work. The entry method is an authorized human
using the authenticated API, for example Swagger `/docs` or a human-operated
local HTTP client in the authorized environment. A consolidated per-decision
human review packet is allowed; it does not delegate approval to an agent or
create a new bulk endpoint. No credential appears in chat, tracked files or
evidence snapshots.

Proposed API additions:

- Existing manager inventory GET returns exact `cleaned_description`, its raw
  UTF-8 SHA-256, coordinate convention, manual rows, current inventory fingerprint,
  source_fingerprint and input_adapter_version. GET performs no writes.
- POST `/matching-inputs/jobs/{job_id}/capabilities` accepts the source/anchor
  fields below, expected_fingerprint, type, classification, literal approved
  review status, review reason and review-packet/ledger reference.
- DELETE `/matching-inputs/jobs/{job_id}/capabilities/{id}` requires current
  expected_fingerprint. Foreign job/row references follow existing 404 hiding;
  unauthenticated requests return 401 and ordinary candidates 403.
- Existing group requests gain one exclusive manual-capability member reference.
  No review/edit/taxonomy endpoint is added for manual rows.

Manual rows are **human-approved required or preferred capabilities only**.
Allowed types remain skill, tool, domain_knowledge and language. Pending,
rejected, unknown-classification or non_requirement proposals stay unentered
in the private ledger. A named human must not sign inventory complete while
any source interpretation/uncertain proposal remains unresolved there. The server
cannot discover unentered private-ledger items; schema acceptance is not proof
of semantic source completeness.

The server sets provenance=`manual_transcription`, authenticated reviewed_by,
immutable reviewer pseudonym/role snapshots and reviewed_at. Clients cannot supply
those fields or claim extractor provenance. Agent/tool draft origin, actual human
operator/reviewer and per-decision approval remain separately bound in the ledger.
Content/review correction uses explicit delete/recreate, never silent mutation
of immutable review attribution. A new row requires a new source check and human
approval; no automatic replay after a successful or uncertain POST.

## Source Coordinates And Validation

The authoritative application source is **Job.cleaned_description**, not the
original PDF, uploaded raw description or local normalized TXT file. Inventory
GET supplies its exact current text and SHA-256. No normalization, trimming,
newline conversion or punctuation removal is applied before hashing/anchoring.

Store separate half-open Unicode code-point ranges:

- capability_start/end for the exact atomic source expression;
- evidence_start/end for its enclosing supporting passage.

Require `0 <= evidence_start <= capability_start < capability_end <= evidence_end
<= len(cleaned_description)`. Capability text and evidence text must equal their
respective source slices exactly. Normalize only the matching key using existing
NFC, casefold and whitespace-collapse behavior, without punctuation stripping.
The server derives that key; it is not an alias supplied to force identity.

Limits, measured in code points: capability text 1-255; normalized key 1-512;
evidence passage 1-1000; review reason 1-1000; opaque ledger reference 1-255.
Hashes are exactly 64 lowercase hexadecimal characters. Offsets are nonnegative
integer columns with positive ordered spans. Reject over-limit values; never
silently clip stored assertions, change source wording or join separated spans.
Snapshots have separate byte limits below. An exact source span proves location,
not that the expression is an independent required/preferred capability; that
semantic decision remains the named human's responsibility.

Local-source anchors are distinct provenance: local source SHA-256, one-based
line range and local code-point range, bound by the private ledger. Corpus entry
must record both local and stored-text anchors; they need not have equal offsets
or hashes. Use separate fields, not one ambiguous source_fingerprint. Non-file
inputs must explicitly record that no local-file anchor exists. The API validates
local metadata structure, not private files it cannot access; the human reviews
their mapping. Do not put private filesystem paths in public responses.

POST locks the owning job using the existing shared input gate, checks
expected_fingerprint, recomputes the cleaned-text hash and validates both slices
before insertion. A database guard independently validates stored-source hash,
range containment and exact source slices against the owning job on INSERT.
Do not revalidate an old row as current merely because the same words appear at
different offsets. A later source mismatch blocks inventory completeness and
makes the job provisional in assessment; it is not an invented zero or an
automatic reanchor. No frozen source changes are authorized by this proposal.

## Duplicate Protection

Manual key: `(compatibility_family(type), normalize(capability_text))` within a
job. Extracted keys use `(compatibility_family(JobSkill.skill_type),
normalize(JobSkill.normalized_text))`, consistently with the existing policy
functions; do not substitute raw text or a different normalization algorithm.
Skill/tool share technical_capability; domain_knowledge and language retain
their existing separate families. Classification and evidence location do not
make the same capability a different arithmetic item.

On creation reject a key already present in any approved compatible extracted
capability, including unknown-classification extracted rows, or another manual
capability. Adopt option (a): also reject manual creation when the same key
matches a pending or rejected extracted occurrence in that job. Record the
requirement as unrepresented in the private ledger; never override or bypass
the extraction review decision through a manual row. Do not reject or rewrite
existing extracted/extracted repetitions.
Do not infer synonym/equivalence matches beyond the existing key. Source-span
overlap alone is a warning: different capabilities may share an evidence passage.

Serialize cross-table checks through the existing job lock/shared gate. Recheck
manual/manual and manual/extracted conflicts at inventory sign-off and
assessment across approved, pending and rejected extracted occurrences,
including conflicts introduced by later extraction/review changes.
Do not break reprocessing by silently deleting either origin. A later conflict
blocks completeness and yields a job-scoped provisional consistency reason,
without rewriting historical results;
other valid jobs can still score. Do not broadly swallow programming failures.

## Fingerprints And Adapter Version

Manual rows belong only in the **inventory fingerprint**, alongside facts,
groups/members and occurrence reviews. Do not add them to the existing
source_fingerprint calculation, retrieval representation or its source hash.
Each manual row separately binds the exact cleaned_description SHA-256.
Adding one manual row must not make unrelated source-bound groups stale merely
by changing source_fingerprint; inventory sign-off does become non-current.

Propose input_adapter_version=`phase6-inputs-v2`, distinct from the unchanged
scoring policy/configuration and retrieval template. Include it in inventory,
capture/run fingerprints and bounded run provenance; persist it relationally on
new inventory reviews and matching runs. New records require the current adapter
version, never a caller override. Previously stored version fields remain NULL
with no fabricated backfill or UPDATE of their recorded evidence/hashes.

Every read-currentness check must explicitly require stored adapter version to
equal the supported current version, in addition to existing fingerprint checks.
Missing/older versions are non-current with a specific version-mismatch reason,
not silently interpreted as current. Existing sign-offs become non-current under
the new inventory contract even with no manual rows; existing runs similarly
become non-current. GET must not rewrite flags, snapshots, scores or historical
input hashes. Explicit later writes/run creation may retire current flags through
the ordinary lifecycle. Historical reads retain recorded provenance and do not
recompute old results as if the new adapter had been used.

## Predeclared Taxonomy And Unchanged Arithmetic

All manual capabilities are unlinked in this extension. No concept/release
columns, fake extracted terms, taxonomy candidates, general relinking or automatic
selection are introduced. The adapter supplies approved Occurrence objects with
empty links and the existing capability type/text, then calls existing identity,
requirement_support and occupational_group functions unchanged.

Exact existing behavior:

- If neither occurrence has an approved link at all, compatible nonempty equal
  normalized text gives text_only_match=1; otherwise not_evidenced=0. Rejected
  and pending links do not block this fallback.
- If only one side has a selected-release approved identity, or selected
  identities share no release, support is identity_incomparable=0.
- Even when neither has a selected-release identity, any approved link outside
  the selected releases blocks fallback and gives identity_incomparable=0.
  An approved historical identity is not erased by excluding its release.
- With comparable selected-release identities on extracted inputs, matching
  concept identity gives 1; conflicting identity gives identity_mismatch=0.
  Equal text cannot override the conflict. Manual rows cannot enter this linked
  branch because they have no links.
- Each approved candidate occurrence is assessed independently; requirement
  support is the existing maximum. Another unlinked candidate occurrence may
  supply text-only support even when a linked occurrence is incomparable.

Identity-incomparable gaps retain that reason and the compared occurrence,
not a claim that approved evidence was absent. They create warnings, not an
extra readiness block, and their zero support participates in the unchanged
group/critical arithmetic. Do not unlink candidate evidence or harmonize text
to avoid these consequences. Existing one-level operators, deduplication,
7:3:2:1 weights, zero numeric dense weight, critical maximum and exact ties remain
unchanged. relationship_allowlist remains exactly empty.

## Deletion, History And Bounded Evidence

Match existing **job-fact** behavior: DELETE requires expected_fingerprint and
refuses a capability that still belongs to any group (409). The human must first
remove its referencing group explicitly. Do not auto-delete groups to make a
standalone capability DELETE succeed. Deletion changes inventory/current-run
fingerprints and invalidates dependent current runs/results in the transaction.
Ordinary deletion preserves historical snapshots, source origin, scores and
arithmetic provenance; it is not a privacy-erasure operation.

Job deletion remains the sensitive-data erasure path. Cascade its manual rows
and owned memberships, and apply the existing job-scoped snapshot erasure and
unreplayable-history behavior, including snapshots whose manual source row was
previously deleted. Preserve permitted non-sensitive arithmetic/policy provenance
and unrelated entities. Do not add candidate-side erasure or a capability-delete
redaction workflow in this extension.

New historical snapshots distinguish extracted_job_skill from
phase6_manual_capability and preserve source row ID, type/classification, source
hash/spans, manual-transcription provenance and immutable reviewer snapshots.
Keep origin in anchor/dedup-reference keys so references cannot resolve to the
wrong source table. Do not rewrite older extracted-origin snapshots to add new
metadata or reinterpret deleted manual evidence as extracted evidence.

Reuse existing bounded excerpts/anchor sharing and snapshot byte constraints.
Retain IDs, source hashes/ranges, origin, identity decisions and reconstruction
references; cap optional display excerpts with explicit omission lengths/hashes.
Do not copy whole job text into every gap, silently truncate scoring inputs or
misreport snapshot failures as concurrency conflicts.

## Proposed Database Integrity Changes

Use a new migration, provisionally `0011_manual_job_capabilities`; do not edit
applied 0009/0010. Required changes are explicit:

1. New job-owned table with CASCADE on owning job deletion; UUID PK and unique
   `(id, job_id)` for ownership references. CHECK type/classification enums,
   literal approved status and manual_transcription provenance, hash syntax,
   text lengths, integer span bounds/containment and canonical family values.
   Store source coordinates, origin, classification, normalized key and review
   fields relationally; JSONB only for bounded evidence/anchor snapshots.
2. Unique `(job_id, compatibility_family, normalized_text)` index on manual
   rows, plus job lookup index. The server derives the canonical key; Unicode
   casefold is not replaced with PostgreSQL lower(). Cross-table creation checks
   use the shared lock and later checks above, not a new uniqueness restriction
   that breaks existing extracted repetitions/reprocessing.
3. Add nullable manual-capability member FK. Replace the two-reference CHECK
   with exactly one of JobSkill/Q-fact/manual-capability references. Add composite
   `(manual_capability_id, job_id)` ownership FK and a partial unique index on
   non-null manual_capability_id for global single-group membership. Preserve
   existing JobSkill and Q-fact exclusivity indexes/composite FKs.
4. The manual member FK uses deferred NO ACTION: a standalone delete cannot
   leave a grouped source absent, but full owning-job cascades can delete all
   owned rows consistently. Service deletion checks reject grouped rows before
   any deletion. Do not implement manual-source ON DELETE CASCADE as an
   indirect grouped-delete bypass.
5. Extend deferred group-integrity validation for manual sources: same job,
   approved status, compatible R/P type, matching required/preferred
   classification and no Q membership. Preserve SINGLE/OR/AND cardinality and
   R-only critical checks. Manual R-group criticality requires the fact-entry
   protocol's explicit source-bound rationale and named human review; no manual
   capability is automatically critical. Direct empty-group/final-member removal
   remains invalid.
6. Extend source-aware cascade handling only as needed for complete job deletion;
   preserve existing extracted/Q-source cleanup and unrelated groups. It must not
   unconditionally remove empty groups or remove a group merely to permit a
   standalone manual-capability delete. Test deferred-FK/cascade ordering.
7. Add the new table to the shared input-write gate and job-scoped current-run
   invalidation triggers. Capability writes must neither touch jobs.updated_at
   nor call retrieval/embedding/prototype invalidators. Source updates already
   invalidate current state; sign-off/assessment must additionally reject manual
   source mismatch and duplicates discovered after later reprocessing.
8. Make manual content, source binding and reviewer attribution immutable after
   insertion; corrections are delete/recreate. Reviewer FK uses SET NULL while
   immutable pseudonym/role/time snapshots survive. Extend existing safe
   reviewer-deletion handling without allowing other field changes as a loophole.
9. Add nullable legacy-compatible input_adapter_version columns to inventory
   reviews and runs. Require a nonempty server-selected version on new records;
   keep it immutable. No migration backfills existing reviews/runs, toggles their
   flags, changes scoring_configurations or rewrites historical snapshots.

Safe downgrade is guarded **before any destructive DDL**. Refuse if manual rows
or manual member references exist, any inventory/run carries the new adapter
version, or retained snapshots depend on manual-origin/adapter-specific data.
Do not silently delete rows, strip snapshots/version tags or drop dependent
history. Only when all new dependent state is absent may downgrade remove new
columns/checks/indexes/table and restore the previous function/trigger definitions.
Any archival/cleanup needed to reach that state requires separate authorization;
downgrade itself never performs it. Prove empty and populated-refusal cases on
disposable PostgreSQL, retaining old state unchanged on refusal.

## Smallest Implementation And Acceptance Scope

Backend work: new model/migration and request schema; manager inventory GET
source fields; POST/DELETE service/repository; group member validation; inventory
and run fingerprints/version currentness; source/duplicate checks; origin-aware
adapter/evidence persistence. Keep routes thin and pure scoring functions intact.
No frontend selection/form implementation, new taxonomy workflow or bulk-entry
framework is included. Existing result rendering must retain/label manual origin
when displaying the new bounded evidence contract; do not fabricate extractor IDs.

Required regressions: permissions and actual reviewer attribution; approved-only
contracts; exact source/hash and Unicode/UTF-16 conversion boundary cases; local
versus stored anchors; length limits; same-job ownership and global membership;
duplicate family/case/NFC/whitespace and later extraction conflicts across all
three review states, including pending/rejected creation refusal and ledger
handling; overlap-only
warnings; classification-consistent groups; unknown ledger sign-off obligations;
rollback/concurrency; grouped-delete refusal and explicit ungrouped deletion;
historical-snapshot preservation and job-erasure redaction; bounded persistence;
old adapter/sign-off/read-only currentness; downgrade refusal without data loss.
Explicitly test downgrade refusal from adapter-version tags alone, even when
manual rows and member references are absent. After member deletion, surviving
historical atomic-result identities must remain distinguishable by source origin
and occurrence reference, without identity collisions or rewritten results.

Prove manual-only changes leave jobs/extraction/reviews, v1/v2 retrieval text and
source hashes, all embeddings, legacy matches, taxonomy histories and frozen
files unchanged. Existing inputs without manual rows must retain the same pure
arithmetic/identity results. Missing-source/duplicate errors are expected
job-scoped provisional consistency states, not reasons to score zero or stop
other valid jobs. No blanket error swallowing.

Conditional/nested/threshold requirements, degree equivalence, non-numeric
experience, occupation identity and all complete-pool readiness gates remain
unresolved exactly as before. This removes only one storage/entry limitation;
it does not promise any candidate will have an evaluable top-20 pool.
