import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BriefcaseBusiness, ExternalLink, FileSearch, Plus, RefreshCw } from "lucide-react";
import { FormEvent, ReactNode, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  archiveJob,
  createJob,
  listJobs,
  listRecommendations,
  RECOMMENDATION_PAGE_SIZES,
  refreshRecommendations,
  setHideBelowExperience,
} from "../api/documents";
import { JobDetailPanel, jobMeta } from "../components/JobDetailPanel";
import { LiveJobImportPanel } from "../components/LiveJobImportPanel";
import { SectionList } from "../components/SectionList";
import { SkillReviewPanel } from "../components/SkillReviewPanel";
import { useAuth } from "../features/auth/AuthProvider";
import type { Job, JobPayload, RecommendationItem, RecommendationList } from "../types/documents";
import { RankBadge } from "../ui/Badges";
import { Chip } from "../ui/Chip";
import { SkillBar } from "../ui/CoverageBar";
import { EmptyState, ErrorText, Notice, Skeleton } from "../ui/Feedback";
import { CardTitle, PageHeader, riseDelay } from "../ui/Page";
import { Pager } from "../ui/Pager";
import { Tip } from "../ui/Tip";
import { coverageView } from "../utils/coverage";
import { isLiveJobSource } from "../utils/reviewStatus";
import { fraction, previewCoverage, topGaps, whatIfSummary } from "../utils/skillMap";

const emptyJob: JobPayload = { title: "", company: "", location: "", employment_type: "", description: "" };

// --- Candidate: ranked list, selected job with its skill map, "what if I learned" ----------------

function JobListCard({ item, index, selected, onSelect, preview }: {
  item: RecommendationItem; index: number; selected: boolean; onSelect: () => void; preview: string | null;
}) {
  const meta = jobMeta(item);
  const view = coverageView(item);
  const shown = previewCoverage(item, preview);
  const basis = view.basis === "required" ? "required" : view.basis === "mentioned" ? "mentioned" : "no skills found";
  return (
    <li className="animate-rise" style={riseDelay(index)}>
      <button
        aria-pressed={selected}
        className={`lift w-full rounded-card border bg-white p-4 text-left ${selected ? "border-ink ring-1 ring-ink" : "border-line"}`}
        onClick={onSelect}
        type="button"
      >
        <div className="flex items-start gap-4">
          <RankBadge rank={item.rank} />
          <div className="min-w-0 flex-1">
            <p className="font-display text-lg font-semibold leading-snug text-ink">{item.job.title}</p>
            {meta ? <p className="mt-0.5 truncate text-sm text-muted">{meta}</p> : null}
          </div>
          <div className="shrink-0 text-right">
            <p className={`numeral text-2xl leading-none ${shown.closes ? "text-gap-text" : "text-ink"}`}>{fraction(shown.counts, shown.closes)}</p>
            <p className="mt-1 text-[11px] text-muted">{basis}</p>
          </div>
        </div>
        <SkillBar className="mt-3" counts={shown.counts} closes={shown.closes} label={view.label} />
      </button>
    </li>
  );
}

function WhatIf({ items, selected, onSelect }: { items: RecommendationItem[]; selected: string | null; onSelect: (skill: string | null) => void }) {
  const gaps = topGaps(items);
  if (!gaps.length) return null;
  return (
    <section aria-labelledby="what-if-heading" className="animate-rise rounded-card border border-line bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 id="what-if-heading" className="flex items-center gap-1.5 font-display text-base font-semibold text-ink">
          What if I learned
          <Tip label="About what if I learned" align="left">
            The most frequent gaps in the matches on this page. Select one to preview coverage; the order never changes.
          </Tip>
        </h2>
        <div className="flex flex-wrap gap-1.5">
          {gaps.map((gap) => (
            <Chip key={gap.label} kind={selected === gap.label ? "preview" : "missing"} onClick={() => onSelect(selected === gap.label ? null : gap.label)}
              pressed={selected === gap.label} title={`Gap in ${gap.count} of ${items.length}`}>
              +{gap.label} <span className="numeral opacity-70">{gap.count}</span>
            </Chip>
          ))}
        </div>
        <p className="ml-auto text-sm font-medium text-gap-text" role="status" aria-live="polite">
          {selected ? whatIfSummary(selected, items) : ""}
        </p>
      </div>
    </section>
  );
}

function summary(data: RecommendationList): string {
  if (!data.results.length) return "0 matches";
  const first = (data.page - 1) * data.page_size + 1;
  const last = first + data.results.length - 1;
  return `${first}–${last} of ${data.total}`;
}

function Controls({ data, pageSize, onPageSize, onFilter, filterPending }: {
  data: RecommendationList | undefined; pageSize: number; onPageSize: (size: number) => void;
  onFilter: (value: boolean) => void; filterPending: boolean;
}) {
  const canFilter = Boolean(data?.has_work_entries_with_occupation);
  return (
    <>
      <span className="flex items-center gap-1.5">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            checked={Boolean(data?.hide_below_experience)}
            className="h-4 w-4 accent-ink"
            disabled={!canFilter || filterPending}
            onChange={(event) => onFilter(event.target.checked)}
            type="checkbox"
          />
          Hide above my experience
        </label>
        <Tip label="About the experience filter" align="right">
          Hides jobs whose stated minimum is above your related experience. Jobs without a stated minimum are never hidden.
          {canFilter ? null : <> Needs <Link className="link" to="/profile#experience">work entries with an occupation</Link>.</>}
        </Tip>
      </span>
      <label className="flex items-center gap-2 text-sm text-ink">
        Per page
        <select className="field py-1.5" onChange={(event) => onPageSize(Number(event.target.value))} value={pageSize}>
          {RECOMMENDATION_PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
        </select>
      </label>
    </>
  );
}

function CandidateJobs({ accessToken }: { accessToken: string }) {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(RECOMMENDATION_PAGE_SIZES[0]);
  const [preview, setPreview] = useState<string | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const query = useQuery({
    queryKey: ["recommendations", page, pageSize],
    queryFn: () => listRecommendations(accessToken, page, pageSize),
    placeholderData: keepPreviousData,
  });
  const filter = useMutation({
    mutationFn: (value: boolean) => setHideBelowExperience(accessToken, value),
    onSuccess: () => {
      setPage(1);
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
  const refresh = useMutation({
    mutationFn: () => refreshRecommendations(accessToken, page, pageSize),
    onSuccess: (data) => {
      // The server clamps the page when fewer jobs are retrieved now.
      queryClient.setQueryData(["recommendations", data.page, data.page_size], data);
      setPage(data.page);
    },
  });

  const data = query.data;
  const wanted = params.get("job");
  const selected = data?.results.find((item) => item.job_id === wanted) ?? data?.results[0];

  function select(item: RecommendationItem) {
    setParams({ job: item.job_id }, { replace: true });
    if (window.matchMedia("(max-width: 1023px)").matches) detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function changePage(next: number) {
    setPage(next);
    setPreview(null);
    setParams({}, { replace: true });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section className="space-y-5" aria-labelledby="jobs-heading">
      <div className="flex animate-rise flex-wrap items-end justify-between gap-4">
        <div>
          <h1 id="jobs-heading" className="text-4xl font-semibold tracking-tight text-ink">Matches</h1>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 text-sm text-muted" role="status">
            <span className="numeral text-ink">{data ? summary(data) : "…"}</span>
            {data?.collapsed_duplicates ? <span>· {data.collapsed_duplicates} repeats folded</span> : null}
            {data && data.unindexed_jobs > 0 ? <span>· {data.unindexed_jobs} preparing</span> : null}
            <Tip label="About the ranking" align="left">
              Ranked by similarity to your profile. Skill coverage explains each job and never changes the order.
              The same posting in several locations is shown once.
            </Tip>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Controls
            data={data}
            filterPending={filter.isPending}
            onFilter={(value) => filter.mutate(value)}
            onPageSize={(size) => { setPageSize(size); setPage(1); setPreview(null); setParams({}, { replace: true }); }}
            pageSize={pageSize}
          />
          <button className="btn-secondary" disabled={refresh.isPending} onClick={() => refresh.mutate()} type="button">
            <RefreshCw size={16} className={refresh.isPending ? "animate-spin" : ""} aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>

      <ErrorText error={query.error ?? refresh.error ?? filter.error} />
      {data?.hide_below_experience && data.hidden_by_experience ? (
        <Notice>
          <span className="numeral">{data.hidden_by_experience}</span> hidden by the experience filter
        </Notice>
      ) : null}

      {query.isLoading ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-3">{[0, 1, 2, 3].map((index) => <Skeleton key={index} className="h-28" />)}</div>
          <Skeleton className="h-[32rem]" />
        </div>
      ) : data && data.status !== "ready" ? (
        <EmptyState
          icon={FileSearch}
          title={data.status === "profile_not_indexed" ? "Preparing your profile" : "No matches yet"}
          action={data.status === "profile_not_indexed" ? undefined : <Link className="btn-primary" to="/profile">My profile</Link>}
        >
          {data.message}
        </EmptyState>
      ) : data && data.results.length === 0 ? (
        <EmptyState icon={FileSearch} title="No matches">
          {data.hide_below_experience ? "All hidden by the experience filter." : null}
        </EmptyState>
      ) : data && selected ? (
        <>
          <WhatIf items={data.results} selected={preview} onSelect={setPreview} />
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <ul className="space-y-3" aria-label="Matches on this page">
              {data.results.map((item, index) => (
                <JobListCard key={item.job_id} index={index} item={item} preview={preview}
                  selected={item.job_id === selected.job_id} onSelect={() => select(item)} />
              ))}
            </ul>
            <div ref={detailRef} className="scroll-mt-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
              <JobDetailPanel
                accessToken={accessToken}
                item={selected}
                preview={preview}
                rankTotal={data.total}
                extra={
                  <details className="text-sm">
                    <summary className="cursor-pointer font-medium text-ink">Evidence</summary>
                    <div className="mt-3">
                      <SkillReviewPanel accessToken={accessToken} canReview={false} liveJob={isLiveJobSource(selected.job.source)} ownerId={selected.job_id} ownerType="job" />
                    </div>
                  </details>
                }
              />
            </div>
          </div>
          <Pager label="Result pages" onPage={changePage} page={data.page} pages={pages} />
        </>
      ) : null}
    </section>
  );
}

// --- Staff: job management -------------------------------------------------------------------------

function StaffJobCard({ job, actions, children }: { job: Job; actions?: ReactNode; children?: ReactNode }) {
  const posted = job.posted_at ? new Date(job.posted_at).toLocaleDateString() : null;
  return (
    <article className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-ink">{job.title}</h3>
          <p className="text-sm text-muted">
            {job.company || "Unknown company"}
            {job.location ? ` · ${job.location}` : ""} · {job.status}
            {posted ? ` · posted ${posted}` : ""}
          </p>
          {job.attribution || job.external_url ? (
            <p className="mt-1 text-xs text-muted">
              {job.attribution ? <>Source: <a className="link" href={job.attribution.url} rel="noopener noreferrer" target="_blank">{job.attribution.name}</a></> : null}
              {job.external_url ? (
                <>
                  {job.attribution ? " · " : ""}
                  <a className="link inline-flex items-center gap-0.5" href={job.external_url} rel="noopener noreferrer" target="_blank">
                    Original posting <ExternalLink size={12} aria-hidden="true" />
                  </a>
                </>
              ) : null}
            </p>
          ) : null}
        </div>
        {actions}
      </div>
      <div className="mt-4"><SectionList sections={job.sections} /></div>
      {children}
    </article>
  );
}

function StaffJobs({ accessToken, isAdmin }: { accessToken: string; isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [job, setJob] = useState<JobPayload>(emptyJob);
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => listJobs(accessToken) });
  const create = useMutation({
    mutationFn: () => createJob(accessToken, job),
    onSuccess: () => {
      setJob(emptyJob);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
  const archive = useMutation({
    mutationFn: (jobId: string) => archiveJob(accessToken, jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
  const update = (field: keyof JobPayload, value: string) => setJob((current) => ({ ...current, [field]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <section className="space-y-6" aria-labelledby="manage-jobs-heading">
      <PageHeader title="Jobs" />
      {isAdmin ? <LiveJobImportPanel accessToken={accessToken} /> : null}
      <form className="card" onSubmit={submit}>
        <CardTitle id="manage-jobs-heading">Create a job</CardTitle>
        <div className="grid gap-4 md:grid-cols-2">
          {(["title", "company", "location", "employment_type"] as const).map((field) => (
            <label key={field} className="text-sm text-ink">
              {{ title: "Job title", company: "Company", location: "Location", employment_type: "Employment type" }[field]}
              <input className="field mt-1 w-full" onChange={(event) => update(field, event.target.value)} value={job[field]} />
            </label>
          ))}
        </div>
        <label className="mt-4 block text-sm text-ink">
          Job description
          <textarea
            className="field mt-1 min-h-44 w-full"
            onChange={(event) => update("description", event.target.value)}
            placeholder="Paste the job ad"
            value={job.description}
          />
        </label>
        <div className="mt-3"><ErrorText error={create.error} /></div>
        <button className="btn-primary mt-4" disabled={create.isPending} type="submit">
          <Plus size={18} aria-hidden="true" /> Create and process
        </button>
      </form>

      <h2 className="text-xl font-semibold text-ink">All jobs <span className="numeral text-muted">{jobs.data?.length ?? ""}</span></h2>
      {jobs.isLoading ? <div className="space-y-4">{[0, 1].map((index) => <Skeleton key={index} className="h-40" />)}</div> : null}
      {jobs.data?.map((item) => (
        <StaffJobCard
          key={item.id}
          job={item}
          actions={
            <button aria-label={`Archive ${item.title}`} className="btn-secondary h-10 w-10 p-0" onClick={() => archive.mutate(item.id)} type="button">
              <Archive size={18} aria-hidden="true" />
            </button>
          }
        >
          <SkillReviewPanel accessToken={accessToken} canReview liveJob={isLiveJobSource(item.source)} ownerId={item.id} ownerType="job" />
        </StaffJobCard>
      ))}
      {jobs.data?.length === 0 ? <EmptyState icon={BriefcaseBusiness} title="No jobs yet" /> : null}
    </section>
  );
}

export function JobsPage() {
  const { accessToken, user } = useAuth();
  const roles = user?.roles.map((role) => role.name) ?? [];
  const isStaff = roles.includes("admin") || roles.includes("researcher");
  // Job matching is for candidate accounts only; staff accounts get 403 from /matches.
  const isCandidate = roles.includes("candidate") && !isStaff;
  if (!accessToken) return null;
  return (
    <div className="space-y-10">
      {isCandidate ? <CandidateJobs accessToken={accessToken} /> : null}
      {isStaff ? <StaffJobs accessToken={accessToken} isAdmin={roles.includes("admin")} /> : null}
    </div>
  );
}
