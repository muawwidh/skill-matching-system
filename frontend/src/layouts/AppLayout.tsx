import { ChevronDown, Info, LogOut, Shield } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";
import { initials } from "../utils/coverage";

/** Logo mark: three dots (have / gap / related) joined by lines — skills linked into a map. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path d="M8 22 L16 9 L25 20 Z" stroke="#12161C" strokeOpacity="0.28" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx="8" cy="22" r="4.2" fill="#0F8A6A" />
      <circle cx="16" cy="9" r="4.2" fill="#E8590C" />
      <circle cx="25" cy="20" r="4.2" fill="#6D4AE0" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2">
      <LogoMark />
      <span className="font-display text-xl font-bold tracking-tight text-ink">SkillGap</span>
    </span>
  );
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-200 ${isActive ? "bg-ink text-white" : "text-muted hover:bg-mist hover:text-ink"}`;

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
        <span className="grid h-9 w-9 place-items-center rounded-full border border-line bg-white font-display text-sm font-semibold text-ink">
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
              <Info size={16} aria-hidden="true" /> About
            </Link>
            <Link className={item} onClick={() => setOpen(false)} to="/privacy">
              <Shield size={16} aria-hidden="true" /> Privacy
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
      <header className="border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-content flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-8">
          <Link to="/dashboard" aria-label="SkillGap dashboard">
            <Wordmark />
          </Link>
          <nav aria-label="Main" className="order-3 flex w-full flex-wrap gap-1 md:order-none md:w-auto">
            <NavLink className={navClass} to="/dashboard">Dashboard</NavLink>
            <NavLink className={navClass} to="/jobs">{isStaff ? "Jobs" : "Matches"}</NavLink>
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
        <p className="flex flex-wrap gap-x-3 border-t border-line pt-5 text-xs text-muted">
          <span>Career guidance only — not a hiring decision.</span>
          <Link className="hover:text-ink" to="/about">About</Link>
          <Link className="hover:text-ink" to="/privacy">Privacy</Link>
        </p>
      </footer>
    </div>
  );
}
