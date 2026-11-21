import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BriefcaseBusiness, ChevronLeft, ChevronRight, ExternalLink, Info, Plus, RefreshCw } from "lucide-react";
import { FormEvent, ReactNode, useState } from "react";

import {
  archiveJob,
  createJob,
  listJobs,
  listRecommendations,
  RECOMMENDATION_PAGE_SIZES,
  refreshRecommendations,
} from "../api/documents";
import { JobMatchPanel } from "../components/JobMatchPanel";
import { SectionList } from "../components/SectionList";
import { LiveJobImportPanel } from "../components/LiveJobImportPanel";
import { SkillReviewPanel } from "../components/SkillReviewPanel";
import { useAuth } from "../features/auth/AuthProvider";
import type { Job, JobPayload, RecommendationList } from "../types/documents";
import { isLiveJobSource } from "../utils/reviewStatus";

const emptyJob: JobPayload = {
  title: "",
  company: "",
  location: "",
  employment_type: "",
  description: "",
};

/** Source attribution and the original posting for live jobs (D053). */
function JobSourceLine({ job }: { job: Job }) {
  if (!job.attribution && !job.external_url) return null;
  const posted = job.posted_at ? new Date(job.posted_at).toLocaleDateString() : null;
  return (
    <p className="mt-1 text-xs text-slate-500">
      {job.attribution ? (
        <>
          Source:{" "}
          <a className="underline" href={job.attribution.url} rel="noopener noreferrer" target="_blank">
            {job.attribution.name}
          </a>
        </>
      ) : null}
      {posted ? ` · posted ${posted}` : ""}
      {job.external_url ? (
        <>
          {" · "}
          <a className="inline-flex items-center gap-0.5 underline" href={job.external_url} rel="noopener noreferrer" target="_blank">
            Original posting
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        </>
      ) : null}
    </p>
  );
}

function JobCard({ job, actions, children }: { job: Job; actions?: ReactNode; children?: ReactNode }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-ink">{job.title}</h2>
          <p className="text-sm text-slate-600">
            {job.company || "Unknown company"}
            {job.location ? ` · ${job.location}` : ""} · {job.status}
          </p>
          <JobSourceLine job={job} />
        </div>
        {actions}
      </div>
      <div className="mt-4">
        <SectionList sections={job.sections} />
      </div>
      {children}
    </article>
  );
}

function RecommendationSummary({ data }: { data: RecommendationList }) {
  if (data.status !== "ready") {
    return (
      <div role="status" className="flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <Info size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
        <p>{data.message}</p>
      </div>
    );
  }
  const first = (data.page - 1) * data.page_size + 1;
  const last = first + data.results.length - 1;
  return (
    <p className="text-sm text-slate-600">
      {data.results.length === 0
        ? "No jobs could be retrieved for your profile."
        : `Showing ${first}–${last} of ${data.total} best-matching jobs (most similar to your matching profile, top ${data.top_n} of ${data.active_jobs} active jobs).`}
      {data.unindexed_jobs > 0
        ? ` ${data.unindexed_jobs} active job${data.unindexed_jobs === 1 ? " is" : "s are"} not yet indexed and cannot be retrieved.`
        : ""}
    </p>
  );
}

function Pager({
  data,
  onPage,
  onPageSize,
}: {
  data: RecommendationList;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const button = "inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 disabled:opacity-40";
  return (
    <nav aria-label="Job result pages" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-5 py-3 text-sm text-slate-600">
      <label className="flex items-center gap-2">
        Jobs per page
        <select
          className="rounded-md border border-slate-300 px-2 py-1"
          onChange={(event) => onPageSize(Number(event.target.value))}
          value={data.page_size}
        >
          {RECOMMENDATION_PAGE_SIZES.map((size) => (
            <option key={size} value={size}>{size}</option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-2">
        <button className={button} disabled={data.page <= 1} onClick={() => onPage(data.page - 1)} type="button">
          <ChevronLeft size={16} aria-hidden="true" />
          Previous
        </button>
        <span aria-current="page">Page {data.page} of {pages}</span>
        <button className={button} disabled={data.page >= pages} onClick={() => onPage(data.page + 1)} type="button">
          Next
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}

export function JobsPage() {
  const { accessToken, user } = useAuth();
  const roles = user?.roles.map((role) => role.name) ?? [];
  const canManageJobs = roles.includes("admin") || roles.includes("researcher");
  // Job matching is for candidate accounts only; staff accounts get 403 from /matches (D049).
  const isCandidate = roles.includes("candidate") && !canManageJobs;
  const queryClient = useQueryClient();
  const [job, setJob] = useState<JobPayload>(emptyJob);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(RECOMMENDATION_PAGE_SIZES[0]);

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => listJobs(accessToken as string),
    enabled: Boolean(accessToken) && canManageJobs,
  });

  const recommendationsQuery = useQuery({
    queryKey: ["recommendations", page, pageSize],
    queryFn: () => listRecommendations(accessToken as string, page, pageSize),
    enabled: Boolean(accessToken) && isCandidate,
    placeholderData: keepPreviousData,
  });

  const createMutation = useMutation({
    mutationFn: () => createJob(accessToken as string, job),
    onSuccess: () => {
      setJob(emptyJob);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (jobId: string) => archiveJob(accessToken as string, jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshRecommendations(accessToken as string, page, pageSize),
    onSuccess: (data) => {
      // The server clamps the page when fewer jobs are retrieved now.
      queryClient.setQueryData(["recommendations", data.page, data.page_size], data);
      setPage(data.page);
    },
  });

  function submitJob(event: FormEvent) {
    event.preventDefault();
    if (canManageJobs) createMutation.mutate();
  }

  function updateJobField(field: keyof JobPayload, value: string) {
    setJob((current) => ({ ...current, [field]: value }));
  }

  const recommendations = recommendationsQuery.data;

  function changePage(next: number) {
    setPage(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function changePageSize(size: number) {
    setPageSize(size);
    setPage(1);
  }

  const pager =
    recommendations && recommendations.total > 0 ? (
      <Pager data={recommendations} onPage={changePage} onPageSize={changePageSize} />
    ) : null;

  return (
    <div className="space-y-6">
      {isCandidate ? (
        <section className="space-y-4" aria-labelledby="recommendations-heading">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h1 id="recommendations-heading" className="text-xl font-semibold text-ink">Jobs for your profile</h1>
              <button
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700"
                disabled={refreshMutation.isPending}
                onClick={() => refreshMutation.mutate()}
                type="button"
              >
                <RefreshCw size={16} className={refreshMutation.isPending ? "animate-spin" : ""} aria-hidden="true" />
                Refresh
              </button>
            </div>
            <div className="mt-3">
              {recommendationsQuery.isLoading ? <p className="text-sm text-slate-500">Loading jobs...</p> : null}
              {recommendationsQuery.error ? (
                <p role="alert" className="text-sm text-red-700">{recommendationsQuery.error.message}</p>
              ) : null}
              {recommendations ? <RecommendationSummary data={recommendations} /> : null}
            </div>
          </div>
          {pager}
          {recommendations?.results.map((item) => (
            <JobCard key={item.job_id} job={item.job}>
              <JobMatchPanel match={item} rankTotal={recommendations.total} />
              {accessToken ? (
                <SkillReviewPanel
                  accessToken={accessToken}
                  canReview={false}
                  liveJob={isLiveJobSource(item.job.source)}
                  ownerId={item.job_id}
                  ownerType="job"
                />
              ) : null}
            </JobCard>
          ))}
          {recommendations && recommendations.results.length > 0 ? pager : null}
        </section>
      ) : null}

      {canManageJobs ? (
        <section className="space-y-4" aria-labelledby="manage-jobs-heading">
          {roles.includes("admin") && accessToken ? <LiveJobImportPanel accessToken={accessToken} /> : null}
          <form className="rounded-lg border border-slate-200 bg-white p-5" onSubmit={submitJob}>
            <div className="flex items-center gap-2">
              <BriefcaseBusiness size={22} className="text-ocean" aria-hidden="true" />
              <h2 id="manage-jobs-heading" className="text-xl font-semibold text-ink">Create Job Description</h2>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <input className="rounded-md border border-slate-300 px-3 py-2" onChange={(event) => updateJobField("title", event.target.value)} placeholder="Job title" value={job.title} />
              <input className="rounded-md border border-slate-300 px-3 py-2" onChange={(event) => updateJobField("company", event.target.value)} placeholder="Company" value={job.company} />
              <input className="rounded-md border border-slate-300 px-3 py-2" onChange={(event) => updateJobField("location", event.target.value)} placeholder="Location" value={job.location} />
              <input className="rounded-md border border-slate-300 px-3 py-2" onChange={(event) => updateJobField("employment_type", event.target.value)} placeholder="Employment type" value={job.employment_type} />
            </div>
            <textarea
              className="mt-4 min-h-44 w-full rounded-md border border-slate-300 px-3 py-2"
              onChange={(event) => updateJobField("description", event.target.value)}
              placeholder="Paste the job description with responsibilities, requirements, and preferred skills"
              value={job.description}
            />
            {createMutation.error ? <p className="mt-3 text-sm text-red-700">{createMutation.error.message}</p> : null}
            <button className="mt-4 flex items-center gap-2 rounded-md bg-ocean px-4 py-2 font-medium text-white" type="submit">
              <Plus size={18} aria-hidden="true" />
              Create and process
            </button>
          </form>

          <h2 className="text-lg font-semibold text-ink">All jobs</h2>
          {jobsQuery.data?.map((item) => (
            <JobCard
              key={item.id}
              job={item}
              actions={
                <button
                  aria-label="Archive job"
                  className="grid h-10 w-10 place-items-center rounded-md border border-slate-300 text-slate-700"
                  onClick={() => archiveMutation.mutate(item.id)}
                  type="button"
                >
                  <Archive size={18} aria-hidden="true" />
                </button>
              }
            >
              {accessToken ? (
                <SkillReviewPanel accessToken={accessToken} canReview liveJob={isLiveJobSource(item.source)} ownerId={item.id} ownerType="job" />
              ) : null}
            </JobCard>
          ))}
          {jobsQuery.data?.length === 0 ? (
            <p className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-500">No jobs created yet.</p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
