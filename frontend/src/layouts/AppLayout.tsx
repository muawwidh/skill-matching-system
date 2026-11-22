import { ChevronDown, Info, LogOut, Shield } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";
import { initials } from "../utils/coverage";

/** Logo mark: three rising bars (skills growing), drawn inline. */
export function LogoMark() {
  return (
    <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal" aria-hidden="true">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="2" y="11" width="4" height="7" rx="1" fill="#FFFFFF" opacity="0.6" />
        <rect x="8" y="7" width="4" height="11" rx="1" fill="#FFFFFF" opacity="0.8" />
        <rect x="14" y="2" width="4" height="16" rx="1" fill="#FFFFFF" />
      </svg>
    </span>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="font-display text-xl font-bold tracking-tight text-ink">SkillGap</span>
    </span>
  );
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? "bg-teal-soft text-teal-text" : "text-muted hover:bg-mist hover:text-ink"}`;

function AccountMenu() {
  const { signOut, user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function handleSignOut() {
    signOut();
    navigate("/login");
  }

  const item = "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-mist";
  return (
    <div className="relative" ref={root}>
      <button
        ref={button}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="Account menu"
        className="flex items-center gap-1 rounded-full p-0.5 pr-2 hover:bg-mist"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <span className="grid h-9 w-9 place-items-center rounded-full bg-night font-display text-sm font-semibold text-white">
          {initials(user?.full_name, user?.email)}
        </span>
        <ChevronDown size={16} className="text-muted" aria-hidden="true" />
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-64 rounded-xl border border-line bg-white p-2 shadow-lg">
          <div className="border-b border-line px-3 pb-2 pt-1">
            <p className="truncate text-sm font-semibold text-ink">{user?.full_name}</p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
          </div>
          <div className="pt-2">
            <Link className={item} onClick={() => setOpen(false)} to="/about">
              <Info size={16} aria-hidden="true" /> About SkillGap
            </Link>
            <Link className={item} onClick={() => setOpen(false)} to="/privacy">
              <Shield size={16} aria-hidden="true" /> Privacy and your data
            </Link>
            <button className={item} onClick={handleSignOut} type="button">
              <LogOut size={16} aria-hidden="true" /> Sign out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function AppLayout() {
  const { user } = useAuth();
  const isStaff = user?.roles.some((role) => role.name === "admin" || role.name === "researcher");

  return (
    <div className="min-h-screen bg-mist">
      <a className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-30 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2" href="#main">
        Skip to content
      </a>
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-content flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-8">
          <Link to="/dashboard" aria-label="SkillGap dashboard">
            <Wordmark />
          </Link>
          <nav aria-label="Main" className="order-3 flex w-full flex-wrap gap-1 md:order-none md:w-auto">
            <NavLink className={navClass} to="/dashboard">Dashboard</NavLink>
            <NavLink className={navClass} to="/jobs">Jobs</NavLink>
            <NavLink className={navClass} to="/profile">My profile</NavLink>
            <NavLink className={navClass} to="/privacy">Privacy</NavLink>
            {isStaff ? <NavLink className={navClass} to="/taxonomy">Taxonomy</NavLink> : null}
          </nav>
          <AccountMenu />
        </div>
      </header>
      <main id="main" className="mx-auto max-w-content px-4 py-8 sm:px-8">
        <Outlet context={{ user }} />
      </main>
      <footer className="mx-auto max-w-content px-4 pb-10 sm:px-8">
        <p className="border-t border-line pt-5 text-sm text-muted">
          Career guidance only — not a hiring decision. Your results are visible only to you.
        </p>
      </footer>
    </div>
  );
}
