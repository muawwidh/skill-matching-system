import { useQuery } from "@tanstack/react-query";
import { Database, FileText, Gauge, LockKeyhole, Network, ServerCog, UserRound } from "lucide-react";
import type { ReactNode } from "react";

import { getSystemOverview } from "../api/documents";
import { DeleteAccountPanel } from "../components/DeleteAccountPanel";
import { useAuth } from "../features/auth/AuthProvider";
import type { LinkCoverage, ReviewCounts, SystemOverview } from "../types/documents";
import { AUTOMATIC_TOOLTIP } from "../utils/reviewStatus";

const of = (count: number, total: number) => `${count} of ${total}`;

function OverviewTable({ title, head, rows }: { title: string; head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      <div className="overflow-x-auto rounded-md border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>{head.map((cell) => <th className="px-3 py-2 font-medium" key={cell}>{cell}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row, index) => (
              <tr key={index}>{row.map((cell, column) => <td className="px-3 py-2 text-slate-700" key={column}>{cell}</td>)}</tr>
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
  // Live-job skills are rarely reviewed: their pending ones read "automatic" (D054).
  liveJobs ? <span title={AUTOMATIC_TOOLTIP}>{of(counts.pending, counts.total)} automatic</span> : of(counts.pending, counts.total),
  of(counts.rejected, counts.total),
];

function jobReviewRows(skills: SystemOverview["skills"]) {
  const groups = skills.job_by_source;
  if (!groups?.manual || !groups.evaluation || !groups.live) return [reviewRow("Job, extracted", skills.job_extracted)];
  return [
    reviewRow("Job, manual", groups.manual),
    reviewRow("Job, evaluation", groups.evaluation),
    reviewRow("Job, live", groups.live, true),
  ];
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
          <span title={Object.entries(release.by_type).map(([type, count]) => `${type}: ${count}`).join("\n")}>
            {release.other}
          </span>,
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
        rows={[
          reviewRow("CV, extracted", skills.cv_extracted),
          reviewRow("CV, added manually", skills.cv_added_manually),
          ...jobReviewRows(skills),
        ]}
      />
      <OverviewTable
        title="Taxonomy links on approved skills"
        head={["Side", "Approved link", "Pending suggestion", "No link"]}
        rows={[linkRow("CV", links.cv), linkRow("Job", links.job)]}
      />
      <p className="text-xs text-slate-500 lg:col-span-2">* {candidates.cvs.failed_note}</p>
    </div>
  );
}

function SystemOverviewSection({ accessToken }: { accessToken: string }) {
  const overview = useQuery({ queryKey: ["admin", "overview"], queryFn: () => getSystemOverview(accessToken) });
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6">
      <div className="mb-4 flex items-center gap-2">
        <ServerCog size={22} className="text-ocean" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-ink">System overview</h2>
      </div>
      {overview.isPending ? <p className="text-sm text-slate-500">Loading counts…</p> : null}
      {overview.error ? <p className="text-sm text-red-700">{overview.error.message}</p> : null}
      {overview.data ? <OverviewTables data={overview.data} /> : null}
    </section>
  );
}

const phaseCards = [
  { title: "Authentication", text: "Registration, login, refresh-token storage, and role-aware access are active.", icon: LockKeyhole },
  { title: "Candidate Shell", text: "Profile and CV workflows are reserved for the document processing phase.", icon: UserRound },
  { title: "Job Workflow", text: "Job management routes and UI will build on this base API structure.", icon: FileText },
  { title: "Taxonomy Base", text: "Local ESCO and O*NET modules are separated for the import phase.", icon: Network },
  { title: "Evaluation", text: "Metrics and reproducibility modules are isolated for future evaluation runs.", icon: Gauge },
  { title: "PostgreSQL", text: "SQLAlchemy and Alembic are configured for versioned database evolution.", icon: Database },
];

export function DashboardPage() {
  const { user, accessToken } = useAuth();
  const isAdmin = user?.roles.some((role) => role.name === "admin") ?? false;
  const isStaff = user?.roles.some((role) => role.name === "admin" || role.name === "researcher") ?? false;
  const isCandidate = user?.roles.some((role) => role.name === "candidate") ?? false;

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <p className="text-sm font-medium uppercase tracking-wide text-ocean">Foundation</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">Welcome, {user?.full_name ?? "candidate"}</h1>
        <p className="mt-3 max-w-3xl text-slate-600">
          Phase 1 establishes the secure app shell required before CV processing, taxonomy linking,
          semantic retrieval, matching, and evaluation are added.
        </p>
      </section>

      {/* Mounted only for administrators, so the overview request is never made for anyone else. */}
      {isAdmin && accessToken ? <SystemOverviewSection accessToken={accessToken} /> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {phaseCards.map((card) => {
          const Icon = card.icon;
          return (
            <article key={card.title} className="rounded-lg border border-slate-200 bg-white p-5">
              <div className="mb-4 grid h-10 w-10 place-items-center rounded-md bg-amber-100 text-ember">
                <Icon size={20} aria-hidden="true" />
              </div>
              <h2 className="text-lg font-semibold text-ink">{card.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{card.text}</p>
            </article>
          );
        })}
      </section>

      {/* Staff accounts carry attributed review decisions and are removed by an administrator. */}
      {isCandidate && !isStaff && accessToken ? <DeleteAccountPanel accessToken={accessToken} /> : null}
    </div>
  );
}
