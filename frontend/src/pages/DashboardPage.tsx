import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BriefcaseBusiness, CheckCircle2, FileSearch, Network } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { getJobPool, getMatchingProfile, getSkillGaps, getSystemOverview, listRecommendations } from "../api/documents";
import { listWorkEntries } from "../api/experience";
import { useAuth } from "../features/auth/AuthProvider";
import { useSkillSummary } from "../hooks/useSkillSummary";
import type { LinkCoverage, RecommendationItem, RecommendationList, ReviewCounts, SkillGaps, SystemOverview } from "../types/documents";
import { RankBadge } from "../ui/Badges";
import { CoverageLegend, SkillBar } from "../ui/CoverageBar";
import { EmptyState, ErrorText, LoadingBlock, Skeleton } from "../ui/Feedback";
import { CardTitle, PageHeader, riseDelay } from "../ui/Page";
import { Tip } from "../ui/Tip";
import { coverageView, locationText } from "../utils/coverage";
import { AUTOMATIC_TOOLTIP } from "../utils/reviewStatus";
import { fraction } from "../utils/skillMap";

// --- Administrator overview (unchanged data, new styling) -----------------------------------------

const of = (count: number, total: number) => `${count} of ${total}`;

function OverviewTable({ title, head, rows }: { title: string; head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-left text-sm">
          <thead className="bg-mist text-[11px] uppercase tracking-[0.08em] text-muted">
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
    <section className="card animate-rise" aria-labelledby="overview-heading">
      <CardTitle id="overview-heading">System overview</CardTitle>
      {overview.isPending ? <LoadingBlock label="Loading counts" lines={6} /> : null}
      <ErrorText error={overview.error} />
      {overview.data ? <OverviewTables data={overview.data} /> : null}
    </section>
  );
}

// --- Candidate dashboard ----------------------------------------------------------------------------

type Step = { title: string; done: boolean; to: string; action: string };

function SetupCard({ steps }: { steps: Step[] }) {
  const done = steps.filter((step) => step.done).length;
  const next = steps.find((step) => !step.done);
  if (!next) return null;
  return (
    <section className="card animate-rise" aria-labelledby="setup-heading">
      <CardTitle id="setup-heading" aside={<span className="numeral text-sm text-muted">{done}/{steps.length}</span>}>Setup</CardTitle>
      <ol className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const isNext = step === next;
          return (
            <li key={step.title} className={`flex items-center gap-2.5 rounded-xl border px-3 py-2.5 ${isNext ? "border-ink" : "border-line"}`}>
              {step.done ? (
                <CheckCircle2 size={18} className="shrink-0 text-have" aria-hidden="true" />
              ) : (
                <span className="numeral grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full border border-idle text-[10px] text-muted" aria-hidden="true">{index + 1}</span>
              )}
              <span className="sr-only">{step.done ? "done:" : isNext ? "next:" : "to do:"}</span>
              <span className={`flex-1 text-sm ${step.done ? "text-muted line-through decoration-line" : "font-medium text-ink"}`}>{step.title}</span>
              {isNext ? (
                <Link className="inline-flex items-center gap-1 text-sm link" to={step.to} aria-label={step.action}>
                  <ArrowRight size={15} aria-hidden="true" />
                </Link>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function MatchRow({ item, index }: { item: RecommendationItem; index: number }) {
  const meta = [item.job.company, locationText(item)].filter(Boolean).join(" · ");
  const view = coverageView(item);
  return (
    <li className="animate-rise" style={riseDelay(index)}>
      <Link className="lift flex items-center gap-4 rounded-xl border border-line bg-white p-4" to={`/jobs?job=${item.job_id}`}>
        <RankBadge rank={item.rank} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-display font-semibold text-ink">{item.job.title}</p>
          {meta ? <p className="truncate text-sm text-muted">{meta}</p> : null}
          <SkillBar className="mt-2.5" counts={view.counts} label={view.label} />
        </div>
        <p className="numeral shrink-0 text-xl text-ink">{fraction(view.counts)}</p>
      </Link>
    </li>
  );
}

function TopMatches({ data, loading }: { data: RecommendationList | undefined; loading: boolean }) {
  const top = data?.results.slice(0, 3) ?? [];
  return (
    <section className="card flex animate-rise flex-col" aria-labelledby="top-matches-heading">
      <CardTitle id="top-matches-heading" aside={top.length ? <Link className="text-sm link" to="/jobs">All matches</Link> : null}>
        Top matches
      </CardTitle>
      {loading ? (
        <div className="space-y-3">{[0, 1, 2].map((index) => <Skeleton key={index} className="h-20" />)}</div>
      ) : top.length ? (
        <>
          <ul className="space-y-2.5">{top.map((item, index) => <MatchRow key={item.job_id} item={item} index={index} />)}</ul>
          <div className="mt-4"><CoverageLegend /></div>
        </>
      ) : (
        <EmptyState icon={FileSearch} title="No matches yet" action={<Link className="btn-primary" to="/profile">My profile</Link>}>
          {data && data.status !== "ready" ? data.message : null}
        </EmptyState>
      )}
    </section>
  );
}

function SkillGapsCard({ data }: { data: SkillGaps }) {
  const most = Math.max(...data.gaps.map((gap) => gap.missing_in), 1);
  return (
    <section className="card flex animate-rise flex-col" aria-labelledby="skill-gaps-heading" style={riseDelay(1)}>
      <CardTitle id="skill-gaps-heading" aside={<Tip label="About top gaps" align="right">Required skills your top {data.of} matches list and your profile does not have. Preview them on Matches with “What if I learned”.</Tip>}>
        Top gaps
      </CardTitle>
      <ol className="space-y-3">
        {data.gaps.map((gap) => (
          <li key={gap.label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium text-ink">{gap.label}</span>
              <span className="numeral text-gap-text">{gap.missing_in}/{data.of}</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-gap-bg" aria-hidden="true">
              <div className="h-1.5 origin-left animate-fill rounded-full bg-gap" style={{ width: `${(gap.missing_in / most) * 100}%` }} />
            </div>
          </li>
        ))}
      </ol>
      <Link className="mt-auto pt-5 text-sm link" to="/jobs">What if I learned</Link>
    </section>
  );
}

function StatCard({ label, value, detail, index }: { label: string; value: ReactNode; detail?: ReactNode; index: number }) {
  return (
    <div className="card animate-rise" style={riseDelay(index)}>
      <p className="eyebrow">{label}</p>
      <p className="numeral mt-2 text-4xl text-ink">{value}</p>
      {detail ? <p className="mt-1 text-sm text-muted">{detail}</p> : null}
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
    { title: "Add a CV", done: hasCv, to: "/profile", action: "Add a CV" },
    { title: pending ? `Review ${pending} skills` : "Review skills", done: Boolean(summary && summary.confirmed > 0 && pending === 0), to: "/profile#skills", action: "Review skills" },
    { title: "See matches", done: Boolean(data?.status === "ready" && data.total > 0), to: "/jobs", action: "See matches" },
    { title: "Add experience", done: (entries.data?.length ?? 0) > 0, to: "/profile#experience", action: "Add experience" },
  ];

  // Related experience: how many top matches that state a minimum you meet.
  const assessed = data?.results.filter((item) => item.related_experience) ?? [];
  const meets = assessed.filter((item) => item.related_experience?.meets_requirement).length;
  const withOccupation = (entries.data ?? []).filter((entry) => entry.occupation).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle={<span role="status">{data?.status === "ready" ? <><span className="numeral text-ink">{data.total}</span> matches</> : data ? data.message : "…"}</span>}
        actions={<Link className="btn-primary" to="/jobs">Matches <ArrowRight size={16} aria-hidden="true" /></Link>}
      />
      <SetupCard steps={steps} />
      <div className={`grid gap-6 ${gaps.data && gaps.data.gaps.length ? "lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]" : ""}`}>
        <TopMatches data={data} loading={recommendations.isLoading} />
        {gaps.data && gaps.data.gaps.length ? <SkillGapsCard data={gaps.data} /> : null}
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        <StatCard index={0} label="Confirmed skills" value={summary ? summary.confirmed : <Skeleton className="h-10 w-16" />}
          detail={summary ? `${summary.linked} linked to ESCO` : null} />
        <StatCard
          index={1}
          label="Experience met"
          value={withOccupation === 0 || !assessed.length ? "—" : `${meets}/${assessed.length}`}
          detail={withOccupation === 0 ? <Link className="link" to="/profile#experience">Add work entries</Link> : assessed.length ? "top matches with a stated minimum" : "no comparable minimum"}
        />
        <StatCard
          index={2}
          label="Jobs searched"
          value={pool.data ? pool.data.live_jobs.toLocaleString() : <Skeleton className="h-10 w-20" />}
          detail={pool.data?.last_import_at ? `updated ${shortDate(pool.data.last_import_at)}` : null}
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
      <PageHeader title="Dashboard" subtitle={user?.full_name} />
      {/* Mounted only for administrators, so the overview request is never made for anyone else. */}
      {isAdmin && accessToken ? <SystemOverviewSection accessToken={accessToken} /> : null}
      <div className="grid gap-6 md:grid-cols-2">
        <Link className="card lift flex items-center justify-between" to="/jobs">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-ink"><BriefcaseBusiness size={18} aria-hidden="true" /> Jobs</h2>
          <ArrowRight size={18} className="text-muted" aria-hidden="true" />
        </Link>
        <Link className="card lift flex items-center justify-between" to="/taxonomy">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-ink"><Network size={18} aria-hidden="true" /> Taxonomy</h2>
          <ArrowRight size={18} className="text-muted" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
