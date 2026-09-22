import { BriefcaseBusiness } from "lucide-react";
import { Link } from "react-router-dom";

type AuthCardProps = {
  title: string;
  subtitle: string;
  footerText: string;
  footerLinkText: string;
  footerHref: string;
  children: React.ReactNode;
};

export function AuthCard({
  title,
  subtitle,
  footerText,
  footerLinkText,
  footerHref,
  children,
}: AuthCardProps) {
  return (
    <main className="grid min-h-screen place-items-center bg-mist px-4 py-10">
      <section className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-md bg-ocean text-white">
            <BriefcaseBusiness size={22} aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-ink">{title}</h1>
            <p className="text-sm text-slate-600">{subtitle}</p>
          </div>
        </div>
        {children}
        <p className="mt-6 text-center text-sm text-slate-600">
          {footerText}{" "}
          <Link className="font-medium text-ocean hover:text-teal-900" to={footerHref}>
            {footerLinkText}
          </Link>
        </p>
      </section>
    </main>
  );
}
