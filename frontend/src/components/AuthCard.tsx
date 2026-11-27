import { Link } from "react-router-dom";

import { Wordmark } from "../layouts/AppLayout";

type AuthCardProps = {
  title: string;
  subtitle?: string;
  footerText: string;
  footerLinkText: string;
  footerHref: string;
  children: React.ReactNode;
};

export function AuthCard({ title, subtitle, footerText, footerLinkText, footerHref, children }: AuthCardProps) {
  return (
    <main className="grid min-h-screen place-items-center bg-mist px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center"><Wordmark /></div>
        <section className="card animate-rise p-8">
          <h1 className="text-3xl font-semibold text-ink">{title}</h1>
          {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
          <div className="mt-6">{children}</div>
          <p className="mt-6 text-center text-sm text-muted">
            {footerText} <Link className="link" to={footerHref}>{footerLinkText}</Link>
          </p>
        </section>
        <p className="mt-6 text-center text-xs text-muted">
          Career guidance only — not a hiring decision · <Link className="hover:text-ink" to="/about">About</Link> ·{" "}
          <Link className="hover:text-ink" to="/privacy">Privacy</Link>
        </p>
      </div>
    </main>
  );
}
