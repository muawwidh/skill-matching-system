import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BriefcaseBusiness, CheckCircle2, Circle, FileSearch, Globe2, Lightbulb, ServerCog, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { getJobPool, getMatchingProfile, getSkillGaps, getSystemOverview, listRecommendations } from "../api/documents";
import { listWorkEntries } from "../api/experience";
import { useAuth } from "../features/auth/AuthProvider";
import { useSkillSummary } from "../hooks/useSkillSummary";
import type { LinkCoverage, RecommendationItem, RecommendationList, ReviewCounts, SkillGaps, SystemOverview } from "../types/documents";
import { RankBadge } from "../ui/Badges";
import { CoverageBar, CoverageLegend } from "../ui/CoverageBar";
import { EmptyState, ErrorText, LoadingBlock, Skeleton } from "../ui/Feedback";
import { CardTitle, PageHeader } from "../ui/Page";
import { coverageView, locationText } from "../utils/coverage";
import { AUTOMATIC_TOOLTIP } from "../utils/reviewStatus";

// --- Administrator overview (unchanged data, new styling) -----------------------------------------

const of = (count: number, total: number) => `${count} of ${total}`;

function OverviewTable({ title, head, rows }: { title: string; head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-left text-sm">
          <thead className="bg-mist text-xs uppercase tracking-wide text-muted">
            <tr>{head.map((cell) => <th className="px-3 py-2 font-medium" key={cell} scope="col">{cell}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row, index) => (
              <tr key={index}>{row.map((cell, column) => <td className="px-3 py-2 text-ink" key={column}>{cell}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const reviewRow = (label: string, counts: ReviewCounts, liveJobs = false) => [
  label,
  of(counts.approved, counts.total),
  // Live-job skills are rarely reviewed: their pending ones read "automatic".
  liveJobs ? <span title={AUTOMATIC_TOOLTIP}>{of(counts.pending, counts.total)} automatic</span> : of(counts.pending, counts.total),
  of(counts.rejected, counts.total),
];

function jobReviewRows(skills: SystemOverview["skills"]) {
  const groups = skills.job_by_source;
  if (!groups?.manual || !groups.evaluation || !groups.live) return [reviewRow("Job, extracted", skills.job_extracted)];
  return [reviewRow("Job, manual", groups.manual), reviewRow("Job, evaluation", groups.evaluation), reviewRow("Job, live", groups.live, true)];
}

const linkRow = (label: string, links: LinkCoverage) => [
  label,
  of(links.approved_link, links.approved_skills),
  of(links.pending_link, links.approved_skills),
  of(links.no_link, links.approved_skills),
];

function OverviewTables({ data }: { data: SystemOverview }) {
  const { taxonomy, candidates, jobs, skills, taxonomy_links: links } = data;
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <OverviewTable
        title="Taxonomy releases"
        head={["Release", "Status", "Skills", "Occupations", "Other"]}
        rows={taxonomy.releases.map((release) => [
          `${release.source} ${release.version}`,
          `${release.status}${release.is_sample ? " (sample data)" : ""}`,
          release.skills,
          release.occupations,
          <span title={Object.entries(release.by_type).map(([type, count]) => `${type}: ${count}`).join("\n")}>{release.other}</span>,
        ])}
      />
      <OverviewTable
        title="Candidates and jobs"
        head={["Item", "Count"]}
        rows={[
          ["Candidate accounts", candidates.accounts],
          ["CVs processed", `${of(candidates.cvs.processed, candidates.cvs.uploaded)} uploaded`],
          ["CVs failed", <span title={candidates.cvs.failed_note}>{of(candidates.cvs.failed, candidates.cvs.uploaded)} uploaded*</span>],
          ["Jobs active", of(jobs.active, jobs.total)],
          ["Jobs archived", of(jobs.archived, jobs.total)],
        ]}
      />
      <OverviewTable
        title="Skill review"
        head={["Skills", "Approved", "Pending", "Rejected"]}
        rows={[reviewRow("CV, extracted", skills.cv_extracted), reviewRow("CV, added manually", skills.cv_added_manually), ...jobReviewRows(skills)]}
      />
      <OverviewTable
        title="Taxonomy links on approved skills"
        head={["Side", "Approved link", "Pending suggestion", "No link"]}
        rows={[linkRow("CV", links.cv), linkRow("Job", links.job)]}
      />
      <p className="text-xs text-muted lg:col-span-2">* {candidates.cvs.failed_note}</p>
    </div>
  );
}

function SystemOverviewSection({ accessToken }: { accessToken: string }) {
  const overview = useQuery({ queryKey: ["admin", "overview"], queryFn: () => getSystemOverview(accessToken) });
  return (
    <section className="card" aria-labelledby="overview-heading">
      <CardTitle id="overview-heading" aside={<ServerCog size={20} className="text-teal" aria-hidden="true" />}>System overview</CardTitle>
      {overview.isPending ? <LoadingBlock label="Loading counts" lines={6} /> : null}
      <ErrorText error={overview.error} />
      {overview.data ? <OverviewTables data={overview.data} /> : null}
    </section>
  );
}

// --- Candidate dashboard ----------------------------------------------------------------------------

type Step = { title: string; text: string; done: boolean; to: string; action: string };

function SetupCard({ steps }: { steps: Step[] }) {
  const done = steps.filter((step) => step.done).length;
  const next = steps.find((step) => !step.done);
  return (
    <section className="card" aria-labelledby="setup-heading">
      <CardTitle id="setup-heading" aside={<span className="text-sm text-muted">{done} of {steps.length} done</span>}>
        Your profile setup
      </CardTitle>
      <div className="flex gap-1.5" role="img" aria-label={`Profile setup: ${done} of ${steps.length} steps done`}>
        {steps.map((step) => (
          <span key={step.title} className={`h-2 flex-1 rounded-sm ${step.done ? "bg-teal" : "bg-neutral-bar"}`} />
        ))}
      </div>
      <ol className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const isNext = step === next;
          return (
            <li
              key={step.title}
              className={`rounded-xl border p-4 ${isNext ? "border-teal bg-teal-soft" : "border-line bg-white"}`}
            >
              <div className="flex items-center gap-2">
                {step.done ? (
                  <CheckCircle2 size={18} className="text-teal" aria-hidden="true" />
                ) : (
                  <Circle size={18} className={isNext ? "text-teal" : "text-muted"} aria-hidden="true" />
                )}
                <span className="text-xs font-semibold uppercase tracking-wide text-muted">Step {index + 1}</span>
                <span className="sr-only">{step.done ? "done" : isNext ? "next" : "to do"}</span>
              </div>
              <p className="mt-2 font-semibold text-ink">{step.title}</p>
              <p className="mt-1 text-sm text-muted">{step.text}</p>
              {isNext ? (
                <Link className="mt-3 inline-flex items-center gap-1 text-sm link" to={step.to}>
                  {step.action} <ArrowRight size={14} aria-hidden="true" />
                </Link>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function MatchRow({ item }: { item: RecommendationItem }) {
  const meta = [item.job.company, locationText(item)].filter(Boolean).join(" · ");
  return (
    <li>
      <Link
        className="flex gap-4 rounded-xl border border-line p-4 transition-colors hover:border-teal hover:bg-mist"
        to={`/jobs?job=${item.job_id}`}
      >
        <RankBadge rank={item.rank} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-ink">{item.job.title}</p>
          {meta ? <p className="truncate text-sm text-muted">{meta}</p> : null}
          <div className="mt-2">
            <CoverageBar view={coverageView(item)} compact />
          </div>
        </div>
      </Link>
    </li>
  );
}

function TopMatches({ data, loading }: { data: RecommendationList | undefined; loading: boolean }) {
  const top = data?.results.slice(0, 3) ?? [];
  return (
    <section className="card flex flex-col" aria-labelledby="top-matches-heading">
      <CardTitle id="top-matches-heading" aside={top.length ? <Link className="text-sm link" to="/jobs">View all</Link> : null}>
        Your top matches
      </CardTitle>
      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((index) => <Skeleton key={index} className="h-20" />)}
        </div>
      ) : top.length ? (
        <>
          <ul className="space-y-3">{top.map((item) => <MatchRow key={item.job_id} item={item} />)}</ul>
          <div className="mt-4"><CoverageLegend /></div>
        </>
      ) : (
        <EmptyState icon={FileSearch} title="No matches yet" action={<Link className="btn-primary" to="/profile">Go to my profile</Link>}>
          {data && data.status !== "ready" ? data.message : "Confirm a few skills on your profile and your best-matching jobs appear here."}
        </EmptyState>
      )}
    </section>
  );
}

function SkillGapsCard({ data }: { data: SkillGaps }) {
  const [first, ...rest] = data.gaps;
  return (
    <section className="card-dark flex flex-col" aria-labelledby="skill-gaps-heading">
      <div className="flex items-center gap-2">
        <Lightbulb size={20} className="text-caution-bar" aria-hidden="true" />
        <h2 id="skill-gaps-heading" className="text-lg font-semibold">Your skill gaps</h2>
      </div>
      <p className="mt-4 font-display text-2xl font-semibold leading-snug">
        Learning {first.label} would close a required gap in {first.missing_in} of your top {data.of} matches.
      </p>
      {rest.length ? (
        <ul className="mt-5 space-y-2 border-t border-white/15 pt-4 text-sm">
          {rest.map((gap) => (
            <li key={gap.label} className="flex justify-between gap-3">
              <span className="font-medium text-white">{gap.label}</span>
              <span className="text-night-muted">missing in {gap.missing_in} of {data.of}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-auto pt-5 text-xs text-night-muted">Required skills your top {data.of} matches list and your profile does not have.</p>
    </section>
  );
}

function StatCard({ icon: Icon, label, value, detail }: { icon: typeof Sparkles; label: string; value: ReactNode; detail: ReactNode }) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 text-muted">
        <Icon size={18} aria-hidden="true" />
        <span className="eyebrow">{label}</span>
      </div>
      <p className="mt-3 font-display text-3xl font-semibold text-ink">{value}</p>
      <p className="mt-1 text-sm text-muted">{detail}</p>
    </div>
  );
}

const shortDate = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

function CandidateDashboard({ accessToken }: { accessToken: string }) {
  const recommendations = useQuery({ queryKey: ["recommendations", 1, 10], queryFn: () => listRecommendations(accessToken, 1, 10) });
  const gaps = useQuery({ queryKey: ["recommendations", "skill-gaps"], queryFn: () => getSkillGaps(accessToken) });
  const pool = useQuery({ queryKey: ["job-pool"], queryFn: () => getJobPool(accessToken) });
  const profile = useQuery({ queryKey: ["matching-profile"], queryFn: () => getMatchingProfile(accessToken) });
  const entries = useQuery({ queryKey: ["work-entries"], queryFn: () => listWorkEntries(accessToken) });
  const { cvs, summary } = useSkillSummary(accessToken);

  const data = recommendations.data;
  const hasCv = (cvs.data?.length ?? 0) > 0;
  const pending = profile.data
    ? profile.data.cvs.reduce((sum, cv) => sum + (cv.skills.pending ?? 0), 0) + (profile.data.manual_skills.pending ?? 0)
    : 0;
  const steps: Step[] = [
    { title: "Upload your CV", text: "Paste or upload a CV with your consent.", done: hasCv, to: "/profile", action: "Add a CV" },
    {
      title: "Review your skills",
      text: pending ? `${pending} skill mention${pending === 1 ? "" : "s"} still need your review.` : "Confirm the skills that were found.",
      done: Boolean(summary && summary.confirmed > 0 && pending === 0),
      to: "/profile#skills",
      action: "Review skills",
    },
    { title: "See your matches", text: "Jobs ranked by how closely they fit your skills.", done: Boolean(data?.status === "ready" && data.total > 0), to: "/jobs", action: "See my matches" },
    { title: "Add work experience", text: "Optional: compare your years with what jobs ask.", done: (entries.data?.length ?? 0) > 0, to: "/profile#experience", action: "Add experience" },
  ];

  const status = !data
    ? "Loading your matches…"
    : data.status === "ready" && data.total > 0
      ? `${data.total} best-matching jobs are ready for you.`
      : data.status === "ready"
        ? "No matching jobs yet."
        : data.message;

  // Related experience: how many top matches that state a minimum you meet.
  const assessed = data?.results.filter((item) => item.related_experience) ?? [];
  const meets = assessed.filter((item) => item.related_experience?.meets_requirement).length;
  const withOccupation = (entries.data ?? []).filter((entry) => entry.occupation).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Welcome back"
        subtitle={<span role="status">{status}</span>}
        actions={<Link className="btn-primary" to="/jobs">See my matches <ArrowRight size={16} aria-hidden="true" /></Link>}
      />
      <SetupCard steps={steps} />
      <div className={`grid gap-6 ${gaps.data && gaps.data.gaps.length ? "lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]" : ""}`}>
        <TopMatches data={data} loading={recommendations.isLoading} />
        {gaps.data && gaps.data.gaps.length ? <SkillGapsCard data={gaps.data} /> : null}
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        <StatCard
          icon={Sparkles}
          label="Confirmed skills"
          value={summary ? summary.confirmed : <Skeleton className="h-9 w-16" />}
          detail={summary ? `${summary.linked} linked to ESCO` : "Loading…"}
        />
        <StatCard
          icon={BriefcaseBusiness}
          label="Related experience"
          value={withOccupation === 0 ? "—" : assessed.length ? `${meets} of ${assessed.length}` : `${withOccupation}`}
          detail={
            withOccupation === 0 ? (
              <Link className="link" to="/profile#experience">Add work entries to see this</Link>
            ) : assessed.length ? (
              "top matches with a stated minimum where you meet it"
            ) : (
              `work entr${withOccupation === 1 ? "y" : "ies"} with an occupation; none of your top matches states a comparable minimum`
            )
          }
        />
        <StatCard
          icon={Globe2}
          label="Jobs searched"
          value={pool.data ? pool.data.live_jobs.toLocaleString() : <Skeleton className="h-9 w-20" />}
          detail={
            pool.data
              ? `live jobs${pool.data.last_import_at ? ` · last updated ${shortDate(pool.data.last_import_at)}` : ""}`
              : "Loading…"
          }
        />
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { user, accessToken } = useAuth();
  const roles = user?.roles.map((role) => role.name) ?? [];
  const isAdmin = roles.includes("admin");
  const isStaff = isAdmin || roles.includes("researcher");
  const isCandidate = roles.includes("candidate") && !isStaff;

  if (isCandidate && accessToken) return <CandidateDashboard accessToken={accessToken} />;
  return (
    <div className="space-y-6">
      <PageHeader title={`Welcome back${user?.full_name ? `, ${user.full_name}` : ""}`} subtitle="Staff account: manage jobs and the taxonomy, and review skill links." />
      {/* Mounted only for administrators, so the overview request is never made for anyone else. */}
      {isAdmin && accessToken ? <SystemOverviewSection accessToken={accessToken} /> : null}
      <div className="grid gap-6 md:grid-cols-2">
        <Link className="card transition-colors hover:border-teal" to="/jobs">
          <h2 className="text-lg font-semibold text-ink">Jobs</h2>
          <p className="mt-1 text-sm text-muted">Create and archive jobs, review job skills and run the live job import.</p>
        </Link>
        <Link className="card transition-colors hover:border-teal" to="/taxonomy">
          <h2 className="text-lg font-semibold text-ink">Taxonomy</h2>
          <p className="mt-1 text-sm text-muted">Taxonomy releases, imports and the review of skill links.</p>
        </Link>
      </div>
    </div>
  );
}
