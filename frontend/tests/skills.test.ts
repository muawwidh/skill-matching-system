import assert from "node:assert/strict";
import { test } from "node:test";

import { summarizeSkills } from "../src/utils/skills.ts";

const skill = (id: string, text: string, review_status: string, source = "extraction") => ({
  id, raw_text: text, normalized_text: text.toLowerCase(), skill_type: "skill", evidence_sentence: "",
  confidence_score: 1, review_status, source,
});
const group = (label: string, occurrences: ReturnType<typeof skill>[], linked = false) => ({
  key: label.toLowerCase(), label, occurrences,
  taxonomy: linked ? { concept_id: "c", release_id: "r", external_id: "x", preferred_label: label, source: "ESCO", version: "1.2.1" } : null,
});

test("skills are merged across CVs and counted once", () => {
  const manual = skill("m1", "Kafka", "approved", "manual_review");
  const summary = summarizeSkills([
    { cvId: "cv1", groups: [group("Python", [skill("1", "Python", "approved")], true), group("SQL", [skill("2", "SQL", "pending")]), group("Kafka", [manual])] },
    { cvId: "cv2", groups: [group("Python", [skill("3", "Python", "pending")], true), group("Excel", [skill("4", "Excel", "rejected")]), group("Kafka", [manual])] },
  ], [manual]);
  assert.deepEqual(summary.skills.map((s) => [s.label, s.kind, s.linked, s.cvIds]), [
    ["Kafka", "added", false, []],
    ["Python", "confirmed", true, ["cv1", "cv2"]],
    ["SQL", "review", false, ["cv1"]],
  ]);
  assert.deepEqual([summary.confirmed, summary.linked, summary.review], [2, 1, 1]);
});

test("manual skills count without any CV", () => {
  const summary = summarizeSkills([], [skill("m", "Go", "approved", "manual_review")]);
  assert.deepEqual([summary.confirmed, summary.skills[0].kind], [1, "added"]);
});
