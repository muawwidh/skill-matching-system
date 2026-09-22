import { Link } from "react-router-dom";

export function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold text-ink">Privacy Notice</h1>
      <p className="mt-4 leading-7 text-slate-700">
        The system is built around explicit consent, data minimization, access control, auditability,
        and candidate deletion rights. Age, gender, religion, nationality, marital status,
        photographs, and unrelated personal characteristics must not influence matching.
      </p>
      <Link className="mt-6 inline-block font-medium text-ocean hover:text-teal-900" to="/dashboard">
        Back to dashboard
      </Link>
    </main>
  );
}
