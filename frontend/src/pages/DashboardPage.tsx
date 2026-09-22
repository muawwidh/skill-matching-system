import { Database, FileText, Gauge, LockKeyhole, Network, UserRound } from "lucide-react";

import { useAuth } from "../features/auth/AuthProvider";

const phaseCards = [
  { title: "Authentication", text: "Registration, login, refresh-token storage, and role-aware access are active.", icon: LockKeyhole },
  { title: "Candidate Shell", text: "Profile and CV workflows are reserved for the document processing phase.", icon: UserRound },
  { title: "Job Workflow", text: "Job management routes and UI will build on this base API structure.", icon: FileText },
  { title: "Taxonomy Base", text: "Local ESCO and O*NET modules are separated for the import phase.", icon: Network },
  { title: "Evaluation", text: "Metrics and reproducibility modules are isolated for future evaluation runs.", icon: Gauge },
  { title: "PostgreSQL", text: "SQLAlchemy and Alembic are configured for versioned database evolution.", icon: Database },
];

export function DashboardPage() {
  const { user } = useAuth();

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
    </div>
  );
}
