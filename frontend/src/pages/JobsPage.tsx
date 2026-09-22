import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BriefcaseBusiness, Plus } from "lucide-react";
import { FormEvent, useState } from "react";

import { archiveJob, createJob, listJobs, listRecommendations, refreshRecommendations } from "../api/documents";
import { JobMatchPanel } from "../components/JobMatchPanel";
import { SectionList } from "../components/SectionList";
import { SkillReviewPanel } from "../components/SkillReviewPanel";
import { useAuth } from "../features/auth/AuthProvider";
import type { JobPayload } from "../types/documents";

const emptyJob: JobPayload = {
  title: "",
  company: "",
  location: "",
  employment_type: "",
  description: "",
};

export function JobsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [job, setJob] = useState<JobPayload>(emptyJob);

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => listJobs(accessToken as string),
    enabled: Boolean(accessToken),
  });

  const recommendationsQuery = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => listRecommendations(accessToken as string),
    enabled: Boolean(accessToken),
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

  const refreshMatchesMutation = useMutation({
    mutationFn: () => refreshRecommendations(accessToken as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  function submitJob(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  function updateJobField(field: keyof JobPayload, value: string) {
    setJob((current) => ({ ...current, [field]: value }));
  }

  return (
    <div className="space-y-6">
      <form className="rounded-lg border border-slate-200 bg-white p-5" onSubmit={submitJob}>
        <div className="flex items-center gap-2">
          <BriefcaseBusiness size={22} className="text-ocean" aria-hidden="true" />
          <h1 className="text-xl font-semibold text-ink">Create Job Description</h1>
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

      <section className="space-y-4">
          {jobsQuery.data?.map((item) => (
            <article key={item.id} className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-ink">{item.title}</h2>
                  <p className="text-sm text-slate-600">{item.company || "Unknown company"} · {item.status}</p>
                </div>
                <button
                  aria-label="Archive job"
                  className="grid h-10 w-10 place-items-center rounded-md border border-slate-300 text-slate-700"
                  onClick={() => archiveMutation.mutate(item.id)}
                  type="button"
                >
                  <Archive size={18} aria-hidden="true" />
                </button>
              </div>
              <div className="mt-4">
                <SectionList sections={item.sections} />
              </div>
              <JobMatchPanel
                isRefreshing={refreshMatchesMutation.isPending}
                match={recommendationsQuery.data?.find((match) => match.job_id === item.id)}
                onRefresh={() => refreshMatchesMutation.mutate()}
              />
              {accessToken ? (
                <SkillReviewPanel accessToken={accessToken} ownerId={item.id} ownerType="job" />
              ) : null}
            </article>
          ))}
          {jobsQuery.data?.length === 0 ? <p className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-500">No jobs created yet.</p> : null}
      </section>
    </div>
  );
}
