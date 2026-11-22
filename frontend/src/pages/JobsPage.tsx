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
import { ExperienceBadge, RankBadge } from "../ui/Badges";
import { Chip } from "../ui/Chip";
import { CoverageBar, CoverageLegend } from "../ui/CoverageBar";
import { EmptyState, ErrorText, Notice, Skeleton } from "../ui/Feedback";
import { CardTitle, PageHeader } from "../ui/Page";
import { Pager } from "../ui/Pager";
import { requiredCounts } from "../utils/coverage";
import { isLiveJobSource } from "../utils/reviewStatus";

const emptyJob: JobPayload = { title: "", company: "", location: "", employment_type: "", description: "" };
const MAX_CHIPS = 6;

// --- Candidate: job list and detail ---------------------------------------------------------------

function JobChips({ item }: { item: RecommendationItem }) {
  const chips = [
    ...item.matched_required.map((skill) => ({ kind: "matched" as const, label: skill.label })),
    ...item.partial_required.map((skill) => ({ kind: "related" as const, label: skill.label })),
    ...item.missing_required.map((skill) => ({ kind: "missing" as const, label: skill.label })),
  ];
  if (!chips.length) return null;
  const shown = chips.slice(0, MAX_CHIPS);
  return (
    <div className="flex flex-wrap gap-1.5">
      {shown.map((chip) => <Chip key={`${chip.kind}-${chip.label}`} kind={chip.kind}>{chip.label}</Chip>)}
      {chips.length > MAX_CHIPS ? <span className="self-center text-xs text-muted">+{chips.length - MAX_CHIPS} more</span> : null}
    </div>
  );
}

function JobListCard({ item, selected, onSelect }: { item: RecommendationItem; selected: boolean; onSelect: () => void }) {
  const meta = jobMeta(item);
  return (
    <li>
      <button
        aria-pressed={selected}
        className={`w-full rounded-card border bg-white p-5 text-left transition-shadow hover:shadow-md ${selected ? "border-2 border-teal shadow-md" : "border-line"}`}
        onClick={onSelect}
        type="button"
      >
        <div className="flex gap-4">
          <RankBadge rank={item.rank} />
          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <p className="font-display text-lg font-semibold leading-snug text-ink">{item.job.title}</p>
              {meta ? <p className="mt-0.5 text-sm text-muted">{meta}</p> : null}
            </div>
            <ExperienceBadge item={item} />
            <CoverageBar counts={requiredCounts(item)} />
            <JobChips item={item} />
          </div>
        </div>
      </button>
    </li>
  );
}

function summary(data: RecommendationList): string {
  if (!data.results.length) return "No jobs to show.";
  const first = (data.page - 1) * data.page_size + 1;
  const last = first + data.results.length - 1;
  return `Showing ${first}–${last} of ${data.total} best-matching jobs · ranked by similarity to your profile`;
}

function Controls({ data, pageSize, onPageSize, onFilter, filterPending }: {
  data: RecommendationList | undefined; pageSize: number; onPageSize: (size: number) => void;
  onFilter: (value: boolean) => void; filterPending: boolean;
}) {
  const canFilter = Boolean(data?.has_work_entries_with_occupation);
  return (
    <>
      <label className="flex items-center gap-2 text-sm text-ink" title="Hides jobs whose stated minimum is above your related experience. Jobs without a stated minimum or occupation are never hidden.">
        <input
          checked={Boolean(data?.hide_below_experience)}
          className="h-4 w-4 accent-teal"
          disabled={!canFilter || filterPending}
          onChange={(event) => onFilter(event.target.checked)}
          type="checkbox"
        />
        Hide jobs above my experience
      </label>
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
    setParams({}, { replace: true });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section className="space-y-6" aria-labelledby="jobs-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 id="jobs-heading" className="text-3xl font-semibold tracking-tight text-ink">Best-matching jobs</h1>
          <p className="mt-1 text-sm text-muted" role="status">
            {data ? summary(data) : "Loading your matches…"}
            {data && data.unindexed_jobs > 0
              ? ` · ${data.unindexed_jobs} active job${data.unindexed_jobs === 1 ? " is" : "s are"} still being prepared`
              : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Controls
            data={data}
            filterPending={filter.isPending}
            onFilter={(value) => filter.mutate(value)}
            onPageSize={(size) => { setPageSize(size); setPage(1); setParams({}, { replace: true }); }}
            pageSize={pageSize}
          />
          <button className="btn-secondary" disabled={refresh.isPending} onClick={() => refresh.mutate()} type="button">
            <RefreshCw size={16} aria-hidden="true" />
            {refresh.isPending ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      <ErrorText error={query.error ?? refresh.error ?? filter.error} />
      {data && !data.has_work_entries_with_occupation && data.status === "ready" ? (
        <p className="text-xs text-muted">
          To hide jobs above your experience, <Link className="link" to="/profile#experience">add work entries with an occupation</Link>.
        </p>
      ) : null}
      {data?.hide_below_experience && data.hidden_by_experience ? (
        <Notice>
          {data.hidden_by_experience} job{data.hidden_by_experience === 1 ? " is" : "s are"} hidden because the stated minimum is above your
          related experience. Positions (#N of {data.total}) count only the jobs shown; jobs without a stated minimum are never hidden.
        </Notice>
      ) : null}

      {query.isLoading ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-4">{[0, 1, 2].map((index) => <Skeleton key={index} className="h-44" />)}</div>
          <Skeleton className="h-[32rem]" />
        </div>
      ) : data && data.status !== "ready" ? (
        <EmptyState
          icon={FileSearch}
          title={data.status === "profile_not_indexed" ? "Your profile is being prepared" : "No matches yet"}
          action={data.status === "profile_not_indexed" ? undefined : <Link className="btn-primary" to="/profile">Go to my profile</Link>}
        >
          {data.message}
        </EmptyState>
      ) : data && data.results.length === 0 ? (
        <EmptyState icon={FileSearch} title="No jobs to show">
          {data.hide_below_experience ? "All jobs are hidden by the experience filter. Turn it off to see them." : "No jobs fit your profile yet. Try again after the next job update."}
        </EmptyState>
      ) : data && selected ? (
        <>
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="space-y-4">
              <CoverageLegend />
              <ul className="space-y-4" aria-label="Jobs on this page">
                {data.results.map((item) => (
                  <JobListCard key={item.job_id} item={item} selected={item.job_id === selected.job_id} onSelect={() => select(item)} />
                ))}
              </ul>
            </div>
            <div ref={detailRef} className="scroll-mt-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
              <JobDetailPanel
                item={selected}
                rankTotal={data.total}
                extra={
                  <details className="border-t border-line pt-4 text-sm">
                    <summary className="cursor-pointer font-medium text-ink">All skills found in this posting</summary>
                    <div className="mt-3">
                      <SkillReviewPanel accessToken={accessToken} canReview={false} liveJob={isLiveJobSource(selected.job.source)} ownerId={selected.job_id} ownerType="job" />
                    </div>
                  </details>
                }
              />
            </div>
          </div>
          <Pager label="Job result pages" onPage={changePage} page={data.page} pages={pages} />
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
      <PageHeader title="Jobs" subtitle="Create, review and archive jobs." />
      {isAdmin ? <LiveJobImportPanel accessToken={accessToken} /> : null}
      <form className="card" onSubmit={submit}>
        <CardTitle id="manage-jobs-heading" aside={<BriefcaseBusiness size={20} className="text-teal" aria-hidden="true" />}>Create a job</CardTitle>
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
            placeholder="Responsibilities, requirements and preferred skills"
            value={job.description}
          />
        </label>
        <div className="mt-3"><ErrorText error={create.error} /></div>
        <button className="btn-primary mt-4" disabled={create.isPending} type="submit">
          <Plus size={18} aria-hidden="true" /> Create and process
        </button>
      </form>

      <h2 className="text-xl font-semibold text-ink">All jobs</h2>
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
      {jobs.data?.length === 0 ? <EmptyState icon={BriefcaseBusiness} title="No jobs yet">Create the first job above.</EmptyState> : null}
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
