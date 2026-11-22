# Design decisions

The decisions that shape the system, each with the reason for it, followed by
approaches that were tried or measured and rejected.

## Decisions

1. **Career guidance, not hiring.** The system helps a candidate understand
   which jobs fit and what to learn; it never selects, rejects or scores
   people. *Reason:* an automated hiring decision would need a level of
   accuracy, fairness evidence and legal basis this system does not have.

2. **Dense retrieval decides the order.** The candidate's confirmed skills and
   each job are embedded with a local model; the top 100 jobs by cosine
   similarity are the ranking, shown in pages. *Reason:* in the offline
   comparison, retrieval ranked relevant jobs far higher than any
   skill-coverage order (see rejected approaches).

3. **Skill coverage explains, never reorders, and there is no match score.**
   Each retrieved job shows "X of Y required skills", the skills the candidate
   has, related skills and missing skills. *Reason:* counts and named skills are
   checkable by the candidate; a weighted percentage would rest on arbitrary
   weights.

4. **Three coverage classes: matched, related, missing.** A skill is related
   when a confirmed skill shares a specific ESCO parent concept with it.
   *Reason:* it credits close skills without counting them as matched; broad ESCO skill groups are excluded because they are too
   wide.

5. **Only confirmed skills count.** Extracted skills are suggestions until the
   candidate confirms them; rejected skills are kept as decisions but never
   used. *Reason:* extraction makes mistakes, and the candidate is the
   authority on their own skills.

6. **Unreviewed skills on live jobs count, but are marked.** *Reason:* about
   1,500 imported postings cannot all be reviewed by hand; marking them
   ("automatically extracted, not reviewed") keeps the explanation honest.

7. **Local, versioned taxonomies.** ESCO 1.2.1 (and optionally O*NET) are
   imported as releases and stored locally; nothing is looked up online while
   matching. Links are approved automatically only when one concept is the
   clear best match with confidence ≥ 0.95; everything else stays reviewable.
   *Reason:* reproducible results, and no silent lowering of quality to
   increase automatic matches.

8. **A pinned local embedding model.** `intfloat/multilingual-e5-small` at a
   fixed revision, run on CPU, with model, revision and template version stored
   with every vector. *Reason:* reproducibility, no data leaving the server,
   and acceptable speed on a laptop.

9. **Automatic re-embedding after every change.** *Reason:* otherwise a
   candidate's ranking silently goes stale until an operator re-indexes.

10. **One profile from all CVs plus skills added by hand.** There is no per-CV
    switch; a candidate who does not want a CV used deletes it. *Reason:*
    simplicity, with "Your matching profile" showing exactly what is used.

11. **Experience is self-entered, explained, and never ranks.** Candidates
    enter job titles, months and an ESCO occupation; years in the same 3-digit
    ISCO group are compared with the job's stated minimum, and an optional
    filter hides jobs above their experience. *Reason:* years of experience
    correlate with age, which must not influence matching; and CVs rarely gave
    usable dated entries.

12. **Live jobs only from public job APIs.** Arbeitnow and public Greenhouse
    boards; English postings in Europe or remote; contact details removed
    before storage; duplicates dropped; a cap with at most 70 % per source.
    *Reason:* lawful, polite collection with a link back to each original
    posting, and a balanced job pool.

13. **The evaluation set is isolated.** The 30 benchmark jobs are a separate
    source, never shown to candidates, and the evaluation searches only them.
    *Reason:* live imports must not change the measured results; this is
    checked byte-for-byte after every relevant change.

14. **Results belong to the candidate.** Rankings and explanations are
    computed on read, not stored, and only the candidate can request them;
    staff see totals only. *Reason:* data minimisation and privacy.

15. **Migrations are explicit.** The backend refuses to start when the
    database schema does not match the code, and never migrates on its own.
    *Reason:* no accidental schema changes on a database with real data.

## Rejected approaches

| Approach | What was measured | Why rejected |
| --- | --- | --- |
| **Ranking by skill coverage** (with or without taxonomy links, with similarity as tie-break) | Offline comparison on the benchmark (7 evaluable queries): Recall@10 0.31 / 0.31 / 0.21 and MRR 0.15 for the three coverage orders, against Recall@10 0.60 and MRR 0.62 for retrieval | Far lower on every metric. For 4 of 8 candidates no confirmed skill matched any job, so the order was decided by ties |
| **Weighted match score** (similarity, required and preferred coverage, occupation, qualification combined with fixed weights) | An earlier prototype score used 2:1 required/preferred weights and 80/50 % cut-offs with no documented basis; coverage on its own ranked far below retrieval (row above); seven judged queries are too few to fit weights | Arbitrary weights would look precise without being so |
| **CV extraction with the ESCO skill vocabulary** | On the 8 evaluation CVs: 56 new terms, but only 70 of 1,275 missing job skills (5.5 %) would become matched | Small gain with many false positives: degree names read as skills, partial phrases ("ide" from "STM32Cube IDE"), plural duplicates |
| **"Related" via any shared ESCO parent** | ESCO skill groups have a median of 13 and up to 217 member skills; they caused 145 of the 185 changes such a rule would make | Too broad. The specific-parent rule changed 40 entries in 36 of 341 profile–job pairs |
| **Reading work experience from CVs** | 4 of 15 development CVs gave dated work entries, and none of their titles linked to an ESCO occupation | Too little to rely on; dates from a CV now only pre-fill the form |
| **4-digit or 2-digit ISCO groups for related experience** | 4 digits separated data scientists (2511) from software developers (2512); 2 digits grouped chemists with civil engineers | 3 digits is the usable middle |
| **Job occupation by agreement of the top-3 suggestions** | On 977 live jobs: 20 more titles got a group (23.5 % → 25.6 %), 5 of them wrong (e.g. "Full Stack Engineer" → engineering professionals) | Little gain, and no confidence threshold separated right from wrong |
| **Job occupation by embedding nearest neighbour** | Every unlinked title got a group, but only 9 of 20 sampled were plausible ("AI R&D Engineer" → animal insemination technician at similarity 0.93); 80 % of similarities fell between 0.87 and 0.93 | Wrong matches scored as high as right ones. Embeddings are used only as extra suggestions the candidate chooses from |
| **Removing whole contact lines from postings** | Removed ordinary sentences in the first import | Only e-mail addresses, phone numbers and names after a contact cue are removed |
| **Approximate vector index (ANN)** | Exact search over 978 jobs takes 12 ms | Not needed at this size; exact search keeps results deterministic |
| **Newest postings first without a per-source limit** | First import: 911 Arbeitnow and 66 Greenhouse jobs | One source dominated; each source is now limited to 70 % of the cap |
