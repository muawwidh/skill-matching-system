import assert from "node:assert/strict";
import { test } from "node:test";

import { endSession } from "../src/features/auth/endSession.ts";

test("sign-out clears local tokens and revokes the refresh token on the server", async () => {
  const calls: string[] = [];
  await endSession("refresh-1", () => calls.push("clear"), async (token) => { calls.push(`revoke ${token}`); });
  assert.deepEqual(calls, ["clear", "revoke refresh-1"]);
});

test("sign-out still clears local tokens when the revoke fails", async () => {
  let cleared = false;
  await endSession("refresh-1", () => { cleared = true; }, async () => { throw new Error("offline"); });
  assert.equal(cleared, true);
});

test("sign-out without a refresh token does not call the server", async () => {
  let revoked = false;
  await endSession(null, () => {}, async () => { revoked = true; });
  assert.equal(revoked, false);
});
