import { ClipboardList, FileUp, LogOut, ScrollText, ShieldCheck } from "lucide-react";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";

export function AppLayout() {
  const { signOut, user } = useAuth();
  const navigate = useNavigate();

  function handleSignOut() {
    signOut();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-mist">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link className="flex items-center gap-3 font-semibold text-ink" to="/dashboard">
            <span className="grid h-10 w-10 place-items-center rounded-md bg-ocean text-white">
              <ClipboardList size={20} aria-hidden="true" />
            </span>
            Skill Gap Job Matching
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link className="flex items-center gap-1 text-slate-600 hover:text-ink" to="/cvs">
              <FileUp size={16} aria-hidden="true" />
              CVs
            </Link>
            <Link className="flex items-center gap-1 text-slate-600 hover:text-ink" to="/jobs">
              <ScrollText size={16} aria-hidden="true" />
              Jobs
            </Link>
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
