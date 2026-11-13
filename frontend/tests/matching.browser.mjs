import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { user, candidate, inventory, jobs, run, fingerprint } from "./fixtures.mjs";

// The browser tool is test-only. Every API request is intercepted; none can
// reach the running application, including unexpected requests.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
let server, browser, origin;
before(async () => {
  server = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)), server: { host: "127.0.0.1", port: 5174, strictPort: false, open: false } });
  await server.listen();
  origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined });
});
after(async () => { await browser?.close(); await server?.close(); });

async function fixture(options = {}) {
  const context = await browser.newContext({ viewport: options.viewport || { width: 1280, height: 900 }, serviceWorkers: "block" });
  await context.addInitScript(() => localStorage.setItem("skillgap.accessToken", "synthetic-token-not-a-credential"));
  const calls = [], unexpected = [], errors = [];
  const state = { user: structuredClone(user), candidate: structuredClone(candidate), inventory: structuredClone(inventory), run: structuredClone(run), ...options };
  await context.route("**/*", async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin === origin) return route.continue();
    const path = url.pathname, method = request.method();
    calls.push({ path, method, body: request.postDataJSON() });
    const send = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body), headers: { "Access-Control-Allow-Origin": "*" } });
    if (state.handler) { const response = await state.handler({ path, method, body: request.postDataJSON(), state }); if (response) return send(response.body, response.status); }
    if (path === "/auth/me") return send(state.user);
    if (path === "/candidates/me") return send({ id: "profile-synthetic" });
    if (path === "/jobs") return send(jobs);
    if (path === "/jobs/job-synthetic/extracted-skills") return send([]);
    if (path === "/matching-runs/current" && method === "GET") return send(state.run || { detail: "No matching run" }, state.run ? 200 : 404);
    if (path === "/matching-runs" && method === "POST") { await new Promise(r => setTimeout(r, 120)); return send(state.run, 201); }
    if (path === "/matching-inputs/candidates/profile-synthetic/facts" && method === "GET") return send(state.candidate);
    if (path === "/matching-inputs/jobs/job-synthetic/inventory" && method === "GET") return send(state.inventory);
    if (method !== "GET" && path.startsWith("/matching-inputs/")) return send({ saved: true }, method === "POST" ? 201 : 200);
    unexpected.push(`${method} ${path}`);
    return send({ detail: "Unexpected mock request; network blocked" }, 500);
  });
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  return { page, state, calls, async close() { await context.close(); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []); } };
}
const writes = calls => calls.filter(call => !["GET", "OPTIONS"].includes(call.method));
async function navigate(f, path) { await f.page.goto(origin + path); await f.page.getByRole("heading", { level: 1 }).waitFor(); }
async function saveAndReload(f, button, path) {
  await Promise.all([f.page.waitForResponse(r => r.request().method() === "GET" && r.url().includes(path)), button.click()]);
}

test("candidate navigation, reload and fact lookup never write or use legacy endpoints", async () => {
  const f = await fixture(); try {
    await navigate(f, "/matching");
    await f.page.getByRole("heading", { name: "Synthetic Software Role · Fixture Company" }).waitFor();
    await f.page.getByRole("button", { name: "Reload current state" }).click();
    await f.page.getByRole("link", { name: "Candidate-confirmed facts" }).click();
    await f.page.getByText("Synthetic unfinished qualification", { exact: true }).waitFor();
    await f.page.getByRole("link", { name: "Matching", exact: true }).click();
    await f.page.getByRole("heading", { name: "Explainable matching" }).waitFor();
    assert.deepEqual(writes(f.calls), []);
    assert.ok(f.calls.every(c => !c.path.startsWith("/matches")));
  } finally { await f.close(); }
});
test("visiting Jobs does not invoke the legacy write-on-GET recommendations", async () => {
  const f = await fixture(); try {
    await navigate(f, "/jobs"); await f.page.getByText("No skills or indicators extracted yet.").waitFor();
    assert.ok(f.calls.every(c => !c.path.startsWith("/matches")));
    assert.equal(writes(f.calls).length, 0);
    await f.page.getByRole("link", { name: "Phase 6 explainable matching" }).click();
    await f.page.getByRole("heading", { name: "current run" }).waitFor();
    assert.ok(f.calls.every(c => !c.path.startsWith("/matches")));
  } finally { await f.close(); }
});
test("run creation is explicit, sends empty body once, and requires confirmation on replacement", async () => {
  const f = await fixture(); try {
    await navigate(f, "/matching");
    await f.page.getByRole("heading", { name: "current run" }).waitFor();
    assert.equal(writes(f.calls).length, 0);
    f.page.once("dialog", dialog => dialog.dismiss());
    await f.page.getByRole("button", { name: "Create matching run" }).click();
    assert.equal(writes(f.calls).length, 0);
    f.page.once("dialog", dialog => dialog.accept());
    await f.page.getByRole("button", { name: "Create matching run" }).click();
    await f.page.getByRole("button", { name: "Create matching run", exact: true }).waitFor();
    assert.deepEqual(writes(f.calls).map(c => [c.path, c.body]), [["/matching-runs", {}]]);
  } finally { await f.close(); }
});
test("double-click with no existing run sends one POST", async () => {
  const f = await fixture({ run: null, handler: async ({ path, method }) => {
    if (path !== "/matching-runs" || method !== "POST") return null;
    await new Promise(resolve => setTimeout(resolve, 200));
    return { status: 201, body: run };
  } }); try {
    await navigate(f, "/matching"); await f.page.getByText(/No matching run yet/).waitFor();
    await f.page.getByRole("button", { name: "Create matching run" }).dblclick();
    await f.page.getByRole("heading", { name: "current run" }).waitFor();
    assert.equal(writes(f.calls).length, 1);
    assert.deepEqual(writes(f.calls)[0].body, {});
  } finally { await f.close(); }
});
test("synchronous repeated activation is guarded; failure and completion permit intentional submissions", async () => {
  let attempts = 0;
  const f = await fixture({ run: null, handler: async ({ path, method }) => {
    if (path !== "/matching-runs" || method !== "POST") return null;
    const attempt = ++attempts;
    await new Promise(resolve => setTimeout(resolve, 150));
    return attempt === 1 ? { status: 500, body: { detail: "Synthetic failure" } } : { status: 201, body: run };
  } }); try {
    await navigate(f, "/matching"); await f.page.getByText(/No matching run yet/).waitFor();
    const burst = () => f.page.evaluate(() => {
      const button = document.querySelector("button.match-primary");
      // Bypass disabled rendering so this exercises the synchronous guard itself.
      for (let i = 0; i < 6; i++) { button.disabled = false; button.click(); }
    });
    const firstResponse = f.page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/matching-runs"));
    await burst();
    await firstResponse;
    assert.equal(attempts, 1);
    await f.page.getByRole("alert").filter({ hasText: "Synthetic failure" }).waitFor();
    await f.page.waitForFunction(() => !document.querySelector("button.match-primary").disabled);
    assert.equal(attempts, 1);
    await burst();
    await f.page.getByRole("heading", { name: "current run" }).waitFor();
    assert.equal(attempts, 2);
    await f.page.waitForFunction(() => !document.querySelector("button.match-primary").disabled);
    f.page.once("dialog", dialog => dialog.accept());
    await Promise.all([f.page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/matching-runs")), f.page.getByRole("button", { name: "Create matching run" }).click()]);
    assert.equal(attempts, 3); assert.equal(writes(f.calls).length, 3);
  } finally { await f.close(); }
});
test("empty and 409 readiness states do not auto-create or retry", async () => {
  const f = await fixture({ run: null, handler: ({ path, method }) => path === "/matching-runs" && method === "POST" ? { status: 409, body: { detail: { code: "not_ready", message: "Candidate embedding is stale" } } } : null });
  try {
    await navigate(f, "/matching"); await f.page.getByText(/No matching run yet/).waitFor();
    await f.page.getByRole("button", { name: "Create matching run" }).click();
    await f.page.getByRole("alert").filter({ hasText: "Candidate embedding is stale" }).waitFor();
    assert.equal(writes(f.calls).length, 1);
    assert.equal(f.calls.filter(c => c.path === "/matching-runs" && c.method === "POST").length, 1);
  } finally { await f.close(); }
});
test("deleted/unreplayable reload removes previously rendered evidence", async () => {
  const f = await fixture(); try {
    await navigate(f, "/matching");
    await f.page.getByText("Components, gaps and evidence", { exact: true }).first().click();
    await f.page.getByText("Matched · R · text only match", { exact: true }).click();
    await f.page.getByText("Synthetic Python evidence.", { exact: true }).first().waitFor();
    f.state.run.current = false; f.state.run.status = "unreplayable";
    await f.page.getByRole("button", { name: "Reload current state" }).click();
    await f.page.getByRole("heading", { name: "unreplayable run" }).waitFor();
    assert.equal(await f.page.getByText("Synthetic Python evidence.", { exact: true }).count(), 0);
    assert.equal(await f.page.getByText("76.92 / 100", { exact: true }).count(), 0);
  } finally { await f.close(); }
});
test("candidate fact submit validates required fields, preserves completion caveats and fingerprint", async () => {
  const f = await fixture(); try {
    await navigate(f, "/matching-facts"); await f.page.getByRole("button", { name: "Add fact" }).waitFor();
    await f.page.getByRole("button", { name: "Add fact" }).click(); assert.equal(writes(f.calls).length, 0);
    await f.page.getByLabel("Statement", { exact: true }).fill("Synthetic unfinished programme");
    await f.page.getByLabel("Evidence reference", { exact: true }).fill("Synthetic line 7");
    await f.page.getByLabel("Completion", { exact: true }).selectOption("in_progress");
    await saveAndReload(f, f.page.getByRole("button", { name: "Add fact" }), "profile-synthetic/facts");
    const body = writes(f.calls)[0].body;
    assert.equal(body.completion, "in_progress"); assert.equal(body.review_status, "pending"); assert.equal(body.duration_months, null);
    assert.equal(body.expected_fingerprint, fingerprint); assert.equal(body.cv_document_id, null);
    assert.equal(writes(f.calls).length, 1);
  } finally { await f.close(); }
});
test("fingerprint conflict blocks replay until explicit reload", async () => {
  const f = await fixture({ handler: ({ path, method }) => path.includes("/facts") && method === "POST" ? { status: 409, body: { detail: "Reviewed-input fingerprint changed" } } : null });
  try {
    await navigate(f, "/matching-facts");
    await f.page.getByLabel("Statement", { exact: true }).fill("Synthetic fact");
    await f.page.getByLabel("Evidence reference", { exact: true }).fill("Line 1");
    await f.page.getByRole("button", { name: "Add fact" }).click();
    await f.page.getByRole("alert").waitFor(); assert.equal(writes(f.calls).length, 1);
    assert.equal(await f.page.getByRole("button", { name: "Add fact" }).isDisabled(), true);
    await f.page.getByRole("button", { name: "Reload current inputs" }).click();
    await f.page.waitForFunction(() => ![...document.querySelectorAll("button")].find(b => b.textContent === "Add fact")?.disabled);
    assert.equal(writes(f.calls).length, 1);
  } finally { await f.close(); }
});
test("ordinary candidate cannot fetch manager inventories", async () => {
  const f = await fixture(); try {
    await f.page.goto(origin + "/job-inventories/job-synthetic");
    await f.page.getByRole("alert").filter({ hasText: "Administrator or researcher" }).waitFor();
    assert.ok(f.calls.every(c => c.path === "/auth/me"));
    assert.equal(await f.page.getByRole("link", { name: "Job inventories" }).count(), 0);
  } finally { await f.close(); }
});
test("researcher without candidate role cannot fetch candidate inputs or runs", async () => {
  const f = await fixture({ user: { ...user, roles: [{ name: "researcher" }] } }); try {
    await f.page.goto(origin + "/matching-facts"); await f.page.getByRole("alert").waitFor();
    await f.page.goto(origin + "/matching"); await f.page.getByRole("alert").waitFor();
    assert.ok(f.calls.every(c => c.path === "/auth/me"));
  } finally { await f.close(); }
});
test("additive candidate/researcher roles retain both owned and job-review navigation", async () => {
  const f = await fixture({ user: { ...user, roles: [{ name: "candidate" }, { name: "researcher" }] } }); try {
    await navigate(f, "/job-inventories/job-synthetic");
    await f.page.getByRole("heading", { name: "Requirement groups" }).waitFor();
    assert.equal(await f.page.getByRole("link", { name: "Matching", exact: true }).count(), 1);
    assert.equal(await f.page.getByRole("link", { name: "Job inventories" }).count(), 1);
    assert.deepEqual(writes(f.calls), []);
  } finally { await f.close(); }
});
test("manager classification/group/inventory forms use current fingerprint and explicit decisions", async () => {
  const f = await fixture({ user: { ...user, roles: [{ name: "admin" }] } }); try {
    await navigate(f, "/job-inventories/job-synthetic");
    const occurrence = f.page.locator("form").filter({ has: f.page.getByRole("heading", { name: /^Python/ }) });
    await occurrence.getByLabel("Matching classification").selectOption("non_requirement");
    await occurrence.getByLabel("Classification review status").selectOption("approved");
    await occurrence.getByLabel("Review reason").fill("Synthetic example, not a requirement");
    await saveAndReload(f, occurrence.getByRole("button"), "job-synthetic/inventory");
    await f.page.getByLabel("Group review status").selectOption("approved");
    await f.page.getByLabel("Python · skill", { exact: true }).check();
    await saveAndReload(f, f.page.getByRole("button", { name: "Add group" }), "job-synthetic/inventory");
    await f.page.getByLabel("Component", { exact: true }).selectOption("Q");
    assert.equal(await f.page.getByLabel(/Explicitly reviewed critical/).count(), 0);
    await f.page.getByLabel("Occupation applicability").selectOption("not_applicable");
    await f.page.getByLabel("Qualification/experience applicability").selectOption("not_applicable");
    await saveAndReload(f, f.page.getByRole("button", { name: "Save inventory review" }), "job-synthetic/inventory");
    const actions = writes(f.calls); assert.equal(actions.length, 3);
    for (const action of actions) assert.equal(action.body.expected_fingerprint, fingerprint);
    assert.equal(actions[0].body.classification, "non_requirement");
    assert.deepEqual(actions[1].body.members, [{ job_skill_id: "skill-synthetic", job_matching_fact_id: null }]);
    assert.equal(actions[2].body.inventory_complete, false); assert.equal(actions[2].body.o_reason, "no_occupation_scope_stated");
    assert.equal(actions[2].body.q_reason, "no_qualification_or_experience_scope_stated");
  } finally { await f.close(); }
});
test("API authorization and absent-resource errors stay visible without exposing cached facts", async () => {
  const f = await fixture(); try {
    await navigate(f, "/matching-facts"); await f.page.getByText("Synthetic unfinished qualification", { exact: true }).waitFor();
    f.state.handler = ({ path }) => path.includes("profile-synthetic/facts") ? { status: 404, body: { detail: "Candidate profile not found" } } : null;
    await f.page.getByRole("button", { name: "Reload current inputs" }).click();
    await f.page.getByRole("alert").waitFor();
    assert.equal(await f.page.getByText("Synthetic unfinished qualification", { exact: true }).count(), 0);
    assert.equal(writes(f.calls).length, 0);
  } finally { await f.close(); }
});
test("401 retrieval error stays visible without a login, mutation or legacy fallback", async () => {
  const f = await fixture({ handler: ({ path }) => path === "/matching-runs/current" ? { status: 401, body: { detail: "Not authenticated" } } : null }); try {
    await navigate(f, "/matching"); await f.page.getByRole("alert").filter({ hasText: "Not authenticated" }).waitFor();
    assert.equal(writes(f.calls).length, 0); assert.ok(f.calls.every(c => !c.path.startsWith("/matches")));
  } finally { await f.close(); }
});
test("failed session lookup displays an error instead of an indefinite loading state", async () => {
  const f = await fixture({ handler: ({ path }) => path === "/auth/me" ? { status: 401, body: { detail: "Session expired" } } : null }); try {
    await f.page.goto(origin + "/matching"); await f.page.getByRole("alert").filter({ hasText: "Session expired" }).waitFor();
    assert.equal(f.calls.length, 1); assert.equal(writes(f.calls).length, 0);
    await f.page.getByRole("button", { name: "Return to sign in" }).click();
    await f.page.waitForURL(origin + "/login");
    assert.equal(await f.page.evaluate(() => localStorage.getItem("skillgap.accessToken")), null);
  } finally { await f.close(); }
});
test("fact deletion requires confirmation and keeps the bound fingerprint", async () => {
  const f = await fixture(); try {
    await navigate(f, "/matching-facts");
    f.page.once("dialog", d => d.dismiss()); await f.page.getByRole("button", { name: /^Delete fact:/ }).click();
    assert.equal(writes(f.calls).length, 0);
    f.page.once("dialog", d => d.accept());
    await saveAndReload(f, f.page.getByRole("button", { name: /^Delete fact:/ }), "profile-synthetic/facts");
    assert.equal(writes(f.calls).length, 1); assert.equal(writes(f.calls)[0].method, "DELETE");
    assert.ok(writes(f.calls)[0].path.endsWith("/facts/fact-synthetic"));
  } finally { await f.close(); }
});
test("fact and inventory forms remain labelled and fit narrow viewports", async () => {
  for (const path of ["/matching-facts", "/job-inventories/job-synthetic"]) {
    const f = await fixture({ user: { ...user, roles: [{ name: "candidate" }, { name: "researcher" }] }, viewport: { width: 390, height: 844 } }); try {
      await navigate(f, path); await f.page.getByRole("button", { name: "Add fact", exact: true }).waitFor();
      const issues = await f.page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth,
        unnamed: [...document.querySelectorAll("input,select,textarea")].filter(e => !e.labels?.length).length }));
      assert.deepEqual(issues, { overflow: false, unnamed: 0 });
      await f.page.screenshot({ path: join(tmpdir(), `phase6-${path.includes("job-inventories") ? "inventory" : "facts"}-390.png`), fullPage: true });
      assert.equal(writes(f.calls).length, 0);
    } finally { await f.close(); }
  }
});
test("responsive rendering has named controls, keyboard access and no page overflow", async () => {
  for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
    const f = await fixture({ viewport }); try {
      await navigate(f, "/matching"); await f.page.getByRole("heading", { name: "current run" }).waitFor();
      await f.page.getByText("Components, gaps and evidence", { exact: true }).first().click();
      await f.page.getByText("Matched · R · text only match", { exact: true }).click();
      const audit = await f.page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth,
        unnamedButtons: [...document.querySelectorAll("button")].filter(b => !b.textContent.trim() && !b.getAttribute("aria-label")).length,
        unnamedFields: [...document.querySelectorAll("input,select,textarea")].filter(e => !e.labels?.length && !e.getAttribute("aria-label")).length }));
      assert.deepEqual(audit, { overflow: false, unnamedButtons: 0, unnamedFields: 0 });
      await f.page.getByRole("button", { name: "Reload current state" }).focus(); await f.page.keyboard.press("Enter");
      await f.page.screenshot({ path: join(tmpdir(), `phase6-matching-${viewport.width}.png`), fullPage: true });
      assert.equal(writes(f.calls).length, 0);
    } finally { await f.close(); }
  }
});
