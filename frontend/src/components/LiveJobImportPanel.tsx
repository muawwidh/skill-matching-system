import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CloudDownload } from "lucide-react";

import { getJobImportStatus, startJobImport, type JobImportRun } from "../api/documents";
import { Tip } from "../ui/Tip";

const sum = (values?: Record<string, number>) => Object.values(values ?? {}).reduce((a, b) => a + b, 0);

function RunSummary({ run }: { run: JobImportRun }) {
  const outcomes = run.outcomes ?? {};
  const errors = Object.entries(run.sources ?? {}).flatMap(([source, r]) => r.errors.map((e) => `${source}: ${e}`));
  const stats: [string, number][] = [
    ["Fetched", run.fetched ?? 0], ["Selected", run.selected ?? 0], ["New", outcomes.created ?? 0],
    ["Updated", outcomes.updated ?? 0], ["Unchanged", outcomes.unchanged ?? 0], ["Reactivated", outcomes.reactivated ?? 0],
    ["Duplicates", outcomes.duplicate_content ?? 0], ["Failed", outcomes.failed ?? 0],
    ["Not English", sum(run.skipped_language)], ["Outside Europe", run.skipped_location ?? 0],
    ["Over source share", run.over_source_share_not_imported ?? 0], ["Archived: not listed", run.archived_not_seen ?? 0],
    ["Archived: over cap", run.archived_over_cap ?? 0], ["Archived: source share", run.archived_over_source_share ?? 0],
  ];
  return (
    <div className="mt-4 space-y-3 text-sm text-ink">
      <p className="text-muted">
        Last run {new Date(run.finished_at ?? run.created_at).toLocaleString()} · {run.status} ·{" "}
        <span className="numeral text-ink">{run.active_live_jobs ?? 0}</span> active
        {run.active_live_jobs_by_source
          ? ` (${Object.entries(run.active_live_jobs_by_source).map(([source, count]) => `${source} ${count}`).join(", ")})`
          : ""}
      </p>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-line px-3 py-2">
            <dt className="eyebrow">{label}</dt>
            <dd className="numeral text-xl">{value}</dd>
          </div>
        ))}
      </dl>
      {errors.length ? <p className="text-gap-text">Source errors: {errors.slice(0, 5).join("; ")}</p> : null}
    </div>
  );
}

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
    <section className="card" aria-labelledby="live-jobs-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CloudDownload size={20} className="text-ink" aria-hidden="true" />
          <h2 id="live-jobs-heading" className="text-lg font-semibold text-ink">Live jobs</h2>
          <Tip label="About the live import" align="left">
            Imports English postings from the Arbeitnow and Greenhouse job APIs, removes contact details, runs skill
            extraction and taxonomy linking, and archives postings that are no longer listed.
          </Tip>
        </div>
        <button
          className="btn-primary px-3 py-1.5"
          disabled={running}
          onClick={() => start.mutate()}
          type="button"
        >
          {running ? "Import running..." : "Run import"}
        </button>
      </div>
      {start.error ? <p role="alert" className="mt-2 text-sm text-miss-text">{start.error.message}</p> : null}
      {latest ? <RunSummary run={latest} /> : <p className="mt-3 text-sm text-muted">No runs yet</p>}
    </section>
  );
}
