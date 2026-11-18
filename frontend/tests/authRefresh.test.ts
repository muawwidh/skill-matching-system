import assert from "node:assert/strict";
import { test } from "node:test";

import { sendWithRefresh, singleFlight } from "../src/api/authRefresh.ts";

const status = (code: number) => new Response(null, { status: code });

test("retries once with the refreshed token after a 401", async () => {
  const sent: (string | null | undefined)[] = [];
  const send = async (token: string | null | undefined) => {
    sent.push(token);
    return status(token === "new" ? 200 : 401);
  };
  const response = await sendWithRefresh(send, "old", async () => "new");
  assert.equal(response.status, 200);
  assert.deepEqual(sent, ["old", "new"]);
});

test("returns the 401 when the refresh fails, without retrying", async () => {
  let calls = 0;
  const send = async () => {
    calls += 1;
    return status(401);
  };
  const response = await sendWithRefresh(send, "old", async () => null);
  assert.equal(response.status, 401);
  assert.equal(calls, 1);
});

test("retries only once even if the retried request is also rejected", async () => {
  let calls = 0;
  let refreshes = 0;
  const send = async () => {
    calls += 1;
    return status(401);
  };
  const response = await sendWithRefresh(send, "old", async () => {
    refreshes += 1;
    return "new";
  });
  assert.equal(response.status, 401);
  assert.deepEqual([calls, refreshes], [2, 1]);
});

test("does not refresh for anonymous requests or non-401 errors", async () => {
  let refreshes = 0;
  const refresh = async () => {
    refreshes += 1;
    return "new";
  };
  assert.equal((await sendWithRefresh(async () => status(401), null, refresh)).status, 401);
  assert.equal((await sendWithRefresh(async () => status(403), "old", refresh)).status, 403);
  assert.equal(refreshes, 0);
});

test("concurrent 401s share one refresh request", async () => {
  let refreshes = 0;
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const refresh = singleFlight(async () => {
    refreshes += 1;
    await gate;
    return "new";
  });
  const send = async (token: string | null | undefined) => status(token === "new" ? 200 : 401);
  const pending = [sendWithRefresh(send, "old", refresh), sendWithRefresh(send, "old", refresh)];
  release();
  const responses = await Promise.all(pending);
  assert.deepEqual(responses.map((r) => r.status), [200, 200]);
  assert.equal(refreshes, 1);
  // After the first refresh settles, a later 401 may refresh again.
  await refresh("new");
  assert.equal(refreshes, 2);
});
