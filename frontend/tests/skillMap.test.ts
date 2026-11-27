import assert from "node:assert/strict";
import { test } from "node:test";

import { areaName, fraction, groupByArea, jobMapNodes, previewCoverage, statusCounts, topGaps, whatIfSummary } from "../src/utils/skillMap.ts";

const ict = { code: "06", label: "information and communication technologies (icts)" };
const mgmt = { code: "S4", label: "management skills" };
const job = (over: Record<string, unknown> = {}) => ({
  coverage_basis: "required",
  matched_required: [{ label: "Python", matched_via: "taxonomy_concept", esco_area: ict }],
  matched_preferred: [],
  partial_required: [{ label: "SQL", candidate_skill: "PostgreSQL", broader_concept: "databases", esco_area: ict }],
  partial_preferred: [],
  missing_required: [{ label: "Docker", checked_via: "skill_name", reviewed: false }],
  missing_preferred: [{ label: "Scrum", checked_via: "taxonomy_concept", esco_area: mgmt }],
  ...over,
});

test("area names: short names by ESCO code, otherwise the label, else Other", () => {
  assert.equal(areaName(ict), "ICT");
  assert.equal(areaName({ code: "", label: "software and applications development (x)" }), "Software and applications development");
  assert.equal(areaName(null), "Other");
});

test("map nodes: have / related / gap from the job, not needed from the profile, grouped by area", () => {
  const nodes = jobMapNodes({ ...job(), not_needed: [{ label: "Excel", esco_area: ict }, { label: "Python", esco_area: ict }] });
  assert.deepEqual(nodes.map((n) => [n.label, n.status, n.required]), [
    ["Python", "have", true], ["SQL", "related", true], ["Docker", "gap", true], ["Scrum", "gap", false],
    ["Excel", "idle", false], ["Python", "idle", false],
  ]);
  assert.match(nodes[1].detail ?? "", /related: you have PostgreSQL \(databases\)/);
  assert.equal(nodes[2].unreviewed, true);
  const groups = groupByArea(nodes);
  // Areas with more job skills first; "Other" (no ESCO area) last; one node per label.
  assert.deepEqual(groups.map((g) => g.name), ["ICT", "Management", "Other"]);
  assert.deepEqual(groups[0].nodes.map((n) => n.label), ["Python", "SQL", "Excel"]);
  assert.deepEqual(statusCounts(nodes), { have: 1, related: 1, gap: 2, idle: 2 });
});

test("what if: top gaps across jobs, preview adds an orange segment, order untouched", () => {
  const a = job();
  const b = job({ missing_required: [{ label: "docker", checked_via: "skill_name" }, { label: "Kafka", checked_via: "skill_name" }] });
  const c = job({ coverage_basis: "mentioned", matched_required: [], partial_required: [], missing_required: [],
    missing_preferred: [{ label: "Kafka", checked_via: "skill_name" }] });
  const items = [a, b, c];
  assert.deepEqual(topGaps(items), [{ label: "Docker", count: 2 }, { label: "Kafka", count: 2 }]);
  // Preferred gaps are not counted when the job has required skills (the bar counts required ones).
  assert.ok(!topGaps(items).some((gap) => gap.label === "Scrum"));
  const preview = previewCoverage(b, "Docker");
  assert.deepEqual(preview, { counts: { matched: 1, related: 1, missing: 1 }, closes: 1 });
  assert.equal(fraction(preview.counts, preview.closes), "2/4");
  assert.equal(fraction(previewCoverage(b, null).counts), "1/4");
  assert.deepEqual(previewCoverage(c, "kafka").closes, 1);
  assert.equal(whatIfSummary("Docker", items), "+Docker → closes a gap in 2 of 3 matches");
  assert.deepEqual(items, [a, b, c]);
  assert.equal(fraction({ matched: 0, related: 0, missing: 0 }), "—");
});
