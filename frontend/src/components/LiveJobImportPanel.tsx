import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CloudDownload } from "lucide-react";

import { getJobImportStatus, startJobImport, type JobImportRun } from "../api/documents";

const sum = (values?: Record<string, number>) => Object.values(values ?? {}).reduce((a, b) => a + b, 0);

function RunSummary({ run }: { run: JobImportRun }) {
  const outcomes = run.outcomes ?? {};
  const errors = Object.entries(run.sources ?? {}).flatMap(([source, r]) => r.errors.map((e) => `${source}: ${e}`));
  return (
    <div className="mt-3 text-sm text-slate-700">
      <p>
        Last run {new Date(run.finished_at ?? run.created_at).toLocaleString()} ({run.status}):{" "}
        {run.fetched ?? 0} fetched, {run.selected ?? 0} selected; {outcomes.created ?? 0} new, {outcomes.updated ?? 0} updated,{" "}
        {outcomes.unchanged ?? 0} unchanged, {outcomes.reactivated ?? 0} reactivated, {outcomes.duplicate_content ?? 0} duplicates,{" "}
        {outcomes.failed ?? 0} failed.
      </p>
      <p>
        Skipped: {sum(run.skipped_language)} not in English, {run.skipped_location ?? 0} outside Europe and not remote.
        Archived: {run.archived_not_seen ?? 0} no longer listed, {run.archived_over_cap ?? 0} over the cap.
        Active live jobs: {run.active_live_jobs ?? 0}.
      </p>
      {errors.length ? <p className="text-amber-800">Source errors: {errors.slice(0, 5).join("; ")}</p> : null}
    </div>
  );
}

/** Administrator: start a live job import and see the latest result (D055). */
export function LiveJobImportPanel({ accessToken }: { accessToken: string }) {
  const cache = useQueryClient();
  const status = useQuery({
    queryKey: ["job-import"],
    queryFn: () => getJobImportStatus(accessToken),
    refetchInterval: (query) => (query.state.data?.running ? 5000 : false),
  });
  const start = useMutation({
    mutationFn: () => startJobImport(accessToken),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["job-import"] }),
  });
  const running = Boolean(status.data?.running) || start.isPending;
  const latest = status.data?.runs[0];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5" aria-labelledby="live-jobs-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CloudDownload size={20} className="text-ocean" aria-hidden="true" />
          <h2 id="live-jobs-heading" className="text-lg font-semibold text-ink">Live jobs</h2>
        </div>
        <button
          className="rounded-md bg-ocean px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          disabled={running}
          onClick={() => start.mutate()}
          type="button"
        >
          {running ? "Import running..." : "Run import"}
        </button>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Imports English postings from the Arbeitnow and Greenhouse job APIs, removes contact details, runs skill
        extraction and taxonomy linking, and archives postings that are no longer listed.
      </p>
      {start.error ? <p role="alert" className="mt-2 text-sm text-red-700">{start.error.message}</p> : null}
      {latest ? <RunSummary run={latest} /> : <p className="mt-3 text-sm text-slate-500">No import has run yet.</p>}
    </section>
  );
}
