import assert from "node:assert/strict";
import { test } from "node:test";

import { isLiveJobSource, reviewStatusLabel } from "../src/utils/reviewStatus.ts";

test("pending reads automatic only on live jobs", () => {
  assert.equal(reviewStatusLabel("pending", true), "automatic");
  assert.equal(reviewStatusLabel("pending", false), "pending");
  assert.equal(reviewStatusLabel("pending"), "pending");
  assert.equal(reviewStatusLabel("approved", true), "approved");
  assert.equal(reviewStatusLabel("rejected", true), "rejected");
});

test("live job sources are everything except manual and evaluation", () => {
  assert.equal(isLiveJobSource("arbeitnow"), true);
  assert.equal(isLiveJobSource("greenhouse"), true);
  assert.equal(isLiveJobSource("manual"), false);
  assert.equal(isLiveJobSource("evaluation"), false);
  assert.equal(isLiveJobSource(undefined), false);
});
