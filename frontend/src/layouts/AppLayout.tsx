import { ClipboardList, Database, FileUp, LogOut, ScrollText, ShieldCheck, ListChecks, Scale } from "lucide-react";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";

export function AppLayout() {
  const { signOut, user } = useAuth();
  const navigate = useNavigate();
  const isTaxonomyAdmin = user?.roles.some((role) => role.name === "admin" || role.name === "researcher");
  const isCandidate = user?.roles.some(role => role.name === "candidate");

  function handleSignOut() {
    signOut();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-mist">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap gap-4 items-center justify-between px-4 py-4">
          <Link className="flex items-center gap-3 font-semibold text-ink" to="/dashboard">
            <span className="grid h-10 w-10 place-items-center rounded-md bg-ocean text-white">
              <ClipboardList size={20} aria-hidden="true" />
            </span>
            Skill Gap Job Matching
          </Link>
          <nav aria-label="Main navigation" className="flex flex-wrap items-center gap-4 text-sm">
            {isCandidate && <Link className="flex items-center gap-1" to="/matching"><Scale size={16} aria-hidden="true" />Matching</Link>}
            {isTaxonomyAdmin && <Link className="flex items-center gap-1" to="/job-inventories"><ListChecks size={16} aria-hidden="true" />Job inventories</Link>}
            <Link className="flex items-center gap-1 text-slate-600 hover:text-ink" to="/cvs">
              <FileUp size={16} aria-hidden="true" />
              CVs
            </Link>
            <Link className="flex items-center gap-1 text-slate-600 hover:text-ink" to="/jobs">
              <ScrollText size={16} aria-hidden="true" />
              Jobs / legacy
            </Link>
            {isTaxonomyAdmin ? (
              <Link className="flex items-center gap-1 text-slate-600 hover:text-ink" to="/taxonomy">
                <Database size={16} aria-hidden="true" />
                Taxonomy
              </Link>
            ) : null}
            <Link className="text-slate-600 hover:text-ink" to="/about">
              About
            </Link>
            <Link className="text-slate-600 hover:text-ink" to="/privacy">
              Privacy
            </Link>
            <button
              aria-label="Sign out"
              className="grid h-10 w-10 place-items-center rounded-md border border-slate-300 text-slate-700 hover:bg-slate-100"
              onClick={handleSignOut}
              type="button"
            >
              <LogOut size={18} aria-hidden="true" />
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-center gap-2 text-sm text-slate-600">
          <ShieldCheck size={18} className="text-ocean" aria-hidden="true" />
          Decision support only. Matching excludes unrelated personal attributes.
        </div>
        <Outlet context={{ user }} />
      </main>
    </div>
  );
}
