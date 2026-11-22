import assert from "node:assert/strict";
import { test } from "node:test";

import { coverageLabel, coverageSegments, experienceBadge, initials, pageList, postedAgo, requiredCounts } from "../src/utils/coverage.ts";

test("one segment per required skill, never a percentage", () => {
  const counts = requiredCounts({ matched_required: [1, 2], partial_required: [3], missing_required: [4, 5, 6] });
  assert.deepEqual(counts, { matched: 2, related: 1, missing: 3 });
  assert.deepEqual(coverageSegments(counts), ["matched", "matched", "related", "missing", "missing", "missing"]);
  assert.equal(coverageLabel(counts), "2 of 6 required skills · 1 related");
  assert.equal(coverageLabel({ matched: 3, related: 0, missing: 1 }), "3 of 4 required skills");
  assert.equal(coverageLabel({ matched: 0, related: 0, missing: 0 }), "No required skills listed");
  assert.ok(!coverageLabel(counts).includes("%"));
});

test("experience badge: meets, below, stated but not compared, none stated", () => {
  const related = (meets: boolean) => ({ meets_requirement: meets, min_required_years: 3, relevant_years: 2.5 });
  assert.deepEqual(experienceBadge({ related_experience: related(true) }).text, "Meets 3+ years");
  assert.equal(experienceBadge({ related_experience: related(true) }).tone, "meets");
  assert.equal(experienceBadge({ related_experience: related(false) }).text, "Below 3+ years");
  assert.equal(experienceBadge({ related_experience: null, min_required_years: 2 }).text, "Asks 2+ years");
  assert.equal(experienceBadge({ related_experience: null, min_required_years: null }).text, "No experience stated");
});

test("posted ago, page list and initials", () => {
  const now = new Date("2026-11-22T12:00:00Z");
  assert.equal(postedAgo("2026-11-22T08:00:00Z", now), "posted today");
  assert.equal(postedAgo("2026-11-21T08:00:00Z", now), "posted yesterday");
  assert.equal(postedAgo("2026-11-12T12:00:00Z", now), "posted 10 days ago");
  assert.equal(postedAgo(null, now), null);
  assert.deepEqual(pageList(1, 1), [1]);
  assert.deepEqual(pageList(5, 10), [1, null, 4, 5, 6, null, 10]);
  assert.deepEqual(pageList(2, 4), [1, 2, 3, 4]);
  assert.equal(initials("Demo Candidate", "x@y"), "DC");
  assert.equal(initials("", "demo@example.com"), "D");
});
