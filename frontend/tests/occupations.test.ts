import assert from "node:assert/strict";
import { test } from "node:test";

import { occupationSearchResults, preselectedOccupation } from "../src/utils/occupations.ts";

const suggestion = (label: string, confidence: number, method: "label" | "embedding" = "label") => ({
  concept_id: label, label, isco_code: "2512", isco_unit_group: "Software developers", confidence, method,
});

test("only a strong string match is preselected", () => {
  assert.equal(preselectedOccupation([suggestion("software developer", 0.98)])?.label, "software developer");
  assert.equal(preselectedOccupation([suggestion("software developer", 0.95)])?.label, "software developer");
  assert.equal(preselectedOccupation([suggestion("software developer", 0.9)]), undefined);
  assert.equal(preselectedOccupation([suggestion("software developer", 0.97, "embedding")]), undefined);
  assert.equal(preselectedOccupation([]), undefined);
});

const concept = (id: string, label: string, type = "occupation") => ({
  id, external_id: id, preferred_label: label, description: "", concept_type: type, language: "en",
  source_code: "ESCO", taxonomy_version: "1.2.1", alternative_labels: [],
});

test("search results keep occupations only, best wording match first, without duplicates", () => {
  const results = occupationSearchResults([
    concept("1", "ICT database developer"),
    concept("2", "database administrator"),
    concept("3", "Python (computer programming)", "skill"),
    concept("2", "database administrator"),
    concept("4", "data analyst"),
    concept("5", "database designer"),
  ], "Database");
  assert.deepEqual(results.map((item) => item.label), [
    "database designer", "database administrator", "ICT database developer", "data analyst"]);
  assert.equal(results[0].isco_code, null);
  assert.equal(occupationSearchResults([concept("1", "a"), concept("2", "b"), concept("3", "c")], "x", 2).length, 2);
});
