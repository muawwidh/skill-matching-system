import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { run, fingerprint, fact } from "./fixtures.mjs";
import type { MatchingRun } from "../src/types/matching";
import { RunDetails, atomicIndex, resolveEvidence } from "../src/components/matching/RunDetails";
import { FactForm } from "../src/components/matching/FactForm";
import { ErrorNotice } from "../src/components/matching/Controls";
import { candidateInputs, createRun, currentRun, inputWriter } from "../src/api/matching";
import { ApiError, apiRequest } from "../src/api/client";
import { register } from "../src/api/auth";
import { reviewTaxonomyLink } from "../src/api/taxonomy";

const fixture = () => structuredClone(run) as MatchingRun;
test("complete and provisional results preserve null, reasons, weights and gaps", () => {
  const html = renderToStaticMarkup(<RunDetails run={fixture()} jobNames={new Map([["job-synthetic", "Synthetic role"]])} />);
  for (const text of ["76.92 / 100", "Unavailable", "Null is not zero", "UI-only ordering", "Required skills", "Qualification / experience", "Matched", "unassessed", "identity incomparable", "Candidate-confirmed evidence", "Bounded excerpt", "Numeric alignment weight: 0", "not hiring probabilities", "Missing/stale job embeddings now: 2"]) assert.ok(html.includes(text), text);
  assert.ok(!html.includes("0 / 100"));
});
test("global anchors resolve candidate evidence in a different result", () => {
  const value = fixture();
  assert.equal(resolveEvidence(value.results[1].gaps[0].atomic_assessments[0], "candidate", atomicIndex(value))?.evidence_sentence, "Synthetic Python evidence.");
});
test("partial and missing gaps retain exact support and identity caveats", () => {
  const value = fixture();
  value.results[0].gaps[0].status = "Partially Covered"; value.results[0].gaps[0].support_fraction = "1/2";
  value.results[1].gaps[0].status = "Missing"; value.results[1].gaps[0].reason_code = "identity_incomparable";
  const html = renderToStaticMarkup(<RunDetails run={value} jobNames={new Map()} />);
  assert.ok(html.includes("Partially Covered")); assert.ok(html.includes("Support: 1/2"));
  assert.ok(html.includes("Missing")); assert.ok(html.includes("identity incomparable"));
  assert.ok(!html.includes("not evidenced in approved profile inputs"));
});
test("missing anchors abstain without inventing evidence", () => {
  const value = fixture(); value.results[0].gaps[0].atomic_assessments = [];
  assert.equal(resolveEvidence(value.results[1].gaps[0].atomic_assessments[0], "candidate", atomicIndex(value)), undefined);
});
test("stale runs do not display recorded alignment as current", () => {
  const value = fixture(); value.current = false; value.status = "stale";
  const html = renderToStaticMarkup(<RunDetails run={value} jobNames={new Map()} />);
  assert.ok(!html.includes("76.92 / 100")); assert.ok(html.includes("historical diagnostics"));
});
test("unreplayable runs suppress snapshots even if payload contains old text", () => {
  const value = fixture(); value.status = "unreplayable"; value.current = false;
  const html = renderToStaticMarkup(<RunDetails run={value} jobNames={new Map()} />);
  assert.ok(!html.includes("Synthetic Python evidence")); assert.ok(!html.includes("76.92")); assert.ok(html.includes("redacted"));
});
test("fact forms label review, completion, source and candidate-confirmed caveats", () => {
  const html = renderToStaticMarkup(<FactForm candidate facts={[fact] as never} disabled={false} save={async () => {}} remove={() => {}} />);
  for (const text of ["Candidate-confirmed facts", "in_progress", "Duration unknown", "Review status", "Evidence reference", "Source CV", "pending"]) assert.ok(html.includes(text), text);
  assert.ok(!html.includes("citizenship")); assert.ok(!html.includes("Eligibility"));
});
test("structured errors remain readable and safely escaped", () => {
  assert.ok(renderToStaticMarkup(<ErrorNotice error={new Error("<script>blocked</script>")} />).includes("&lt;script&gt;"));
});
test("matching API methods use exact endpoints and fingerprinted writes", async () => {
  const calls: { url: string; options?: RequestInit }[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => { calls.push({ url: String(url), options }); return new Response("{}", { status: 200 }); };
  try {
    await currentRun("synthetic"); await createRun("synthetic"); await candidateInputs("synthetic", "owned");
    const writer = inputWriter("synthetic", "jobs", "job", fingerprint);
    await writer.fact({ ...fact, id: undefined } as never);
    await writer.classify("skill", "non_requirement", "approved", "Not a requirement");
    await writer.inventory({ review_status: "pending", inventory_complete: false, o_applicability: "unknown", q_applicability: "unknown", o_reason: null, q_reason: null });
    await writer.remove("groups", "group");
    assert.equal(calls[0].url, "http://mock.invalid/matching-runs/current"); assert.equal(calls[0].options?.method, undefined);
    assert.equal(calls[1].options?.method, "POST"); assert.equal(calls[1].options?.body, "{}");
    assert.ok(calls[2].url.endsWith("/matching-inputs/candidates/owned/facts"));
    for (const call of calls.slice(3, 6)) assert.equal(JSON.parse(String(call.options?.body)).expected_fingerprint, fingerprint);
    assert.ok(calls[6].url.endsWith(`?expected_fingerprint=${fingerprint}`));
    assert.ok(calls.every(c => !c.url.includes("/matches/")));
  } finally { globalThis.fetch = original; }
});
test("shared API object/list errors remain readable without matching guidance", async () => {
  const original = globalThis.fetch;
  try {
    for (const detail of [{ code: "matching_concurrency_conflict", message: "Inputs changed" }, [{ loc: ["body", "statement"], msg: "Required" }]]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail }), { status: 409 });
      await assert.rejects(() => apiRequest("/mock"), (error: unknown) => error instanceof ApiError && !error.message.includes("[object Object]") && !error.message.includes("Reload current inputs"));
    }
  } finally { globalThis.fetch = original; }
});
test("registration, taxonomy and retrieval 409 messages are not rewritten", async () => {
  const original = globalThis.fetch;
  try {
    const cases: [string, () => Promise<unknown>][] = [
      ["Email already registered.", () => register({ email: "synthetic@example.test", password: "synthetic", full_name: "Synthetic" })],
      ["Selection changed; reload taxonomy review.", () => reviewTaxonomyLink("synthetic", "link", "rejected")],
      ["Candidate index is not ready; index explicitly.", () => apiRequest("/retrieval/jobs?limit=5")],
    ];
    for (const [message, request] of cases) {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail: message }), { status: 409 });
      await assert.rejects(request, (error: unknown) => error instanceof ApiError && error.status === 409 && error.message === message);
    }
  } finally { globalThis.fetch = original; }
});
test("only Phase 6 conflicts receive reload guidance without duplicated punctuation", async () => {
  const original = globalThis.fetch;
  try {
    const writer = inputWriter("synthetic", "jobs", "job", fingerprint);
    for (const request of [() => createRun("synthetic"), () => writer.classify("skill", "unknown", "pending", "Unresolved"), () => writer.remove("facts", "fact")]) {
      for (const message of ["Inputs changed", "Inputs changed.", "Inputs changed!"]) {
        globalThis.fetch = async () => new Response(JSON.stringify({ detail: { message } }), { status: 409 });
        const expected = `${message}${/[.!?]$/.test(message) ? " " : ". "}Reload current inputs before trying again; the request was not retried.`;
        await assert.rejects(request, (error: unknown) => error instanceof ApiError && error.status === 409 && error.message === expected);
      }
    }
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Invalid matching input" }), { status: 422 });
    await assert.rejects(() => createRun("synthetic"), (error: unknown) => error instanceof ApiError && error.message === "Invalid matching input");
  } finally { globalThis.fetch = original; }
});
test("Phase 6 pages contain no legacy calls or automatic mutation effects", () => {
  for (const path of ["MatchingPage.tsx", "MatchingFactsPage.tsx", "JobInventoryPage.tsx"]) {
    const text = readFileSync(new URL(`../src/pages/${path}`, import.meta.url), "utf8");
    assert.doesNotMatch(text, /listRecommendations|refreshRecommendations|useEffect|\/matches\//);
    assert.match(text, /retry: false/);
  }
});
