import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, RotateCw } from "lucide-react";
import { useRef } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { listJobs } from "../api/documents";
import { createRun, currentRun } from "../api/matching";
import { ErrorNotice, Loading } from "../components/matching/Controls";
import { RunDetails } from "../components/matching/RunDetails";
import { useAuth } from "../features/auth/AuthProvider";

export function MatchingPage() {
  const { accessToken, user } = useAuth();
  const allowed = user?.roles.some(r => r.name === "candidate");
  const client = useQueryClient();
  const submitting = useRef(false);
  const key = ["matching-run", user?.id];
  const run = useQuery({ queryKey: key, queryFn: () => currentRun(accessToken!), enabled: Boolean(allowed && accessToken), retry: false, refetchOnWindowFocus: false });
  const jobs = useQuery({ queryKey: ["matching-job-labels", user?.id], queryFn: () => listJobs(accessToken!), enabled: Boolean(allowed && accessToken), retry: false });
  const action = useMutation({ mutationFn: () => createRun(accessToken!), retry: false,
    onSuccess: data => client.setQueryData(key, data),
    onError: () => { void client.invalidateQueries({ queryKey: key }); } });
  async function submitRun() {
    if (submitting.current || run.isFetching) return;
    if (run.data && !window.confirm("Create a new matching run from current reviewed inputs? The previous run remains history.")) return;
    // Set synchronously: React's pending render alone cannot serialize clicks.
    submitting.current = true;
    try {
      await action.mutateAsync();
    } catch {
      // The mutation exposes the error; never replay an uncertain request.
    } finally {
      submitting.current = false;
    }
  }
  if (!user) return <Loading />;
  if (!allowed) return <p role="alert">Candidate role required. Matching runs are available only to the owning candidate.</p>;
  const empty = run.error instanceof ApiError && run.error.status === 404;
  return <div className="matching-page"><div className="match-summary"><div><h1>Explainable matching</h1><p>Phase 6 · matching-policy-v1</p></div><Link to="/matching-facts">Candidate-confirmed facts</Link></div>
    <p>Only approved evidence contributes. Pending and rejected evidence is not scored. Dense retrieval selects the pool; it contributes no numeric weight to final alignment.</p>
    <p className="match-muted">Private evidence: restricted candidate/job material must remain within its authorized environment. Candidate-confirmed claims are not independently verified.</p>
    <div className="match-actions">
      <button type="button" className="match-primary" disabled={action.isPending || run.isFetching} onClick={() => { void submitRun(); }}><Play size={16} aria-hidden="true" />{action.isPending ? "Creating run..." : "Create matching run"}</button>
      <button type="button" disabled={action.isPending || run.isFetching} onClick={() => { void run.refetch(); action.reset(); }}><RotateCw size={16} aria-hidden="true" />Reload current state</button>
    </div>
    <ErrorNotice error={action.error || (!empty ? run.error : null)} />
    {jobs.error && <p role="alert">Job names unavailable. Results retain their recorded evidence and currentness.</p>}
    {run.isLoading && <Loading />}
    {empty && <p>No matching run yet. Create one only when your reviewed evidence and indexes are ready.</p>}
    {run.data && !run.error && <RunDetails run={run.data} jobNames={new Map(jobs.data?.map(j => [j.id, `${j.title} · ${j.company || "Company unspecified"}`]))} />}
    <footer className="match-section"><p>Legacy prototype recommendations are separate from Phase 6 alignment.</p><Link to="/jobs">Jobs and legacy prototype</Link></footer>
  </div>;
}
