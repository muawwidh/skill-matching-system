import { Link } from "react-router-dom";

export function AboutPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold text-ink">About</h1>
      <p className="mt-4 leading-7 text-slate-700">
        This research application combines dense retrieval, local occupational taxonomies, and
        explainable skill gap analysis to help candidates understand job fit. It is designed for
        career guidance and decision support, not automated hiring decisions.
      </p>
      <Link className="mt-6 inline-block font-medium text-ocean hover:text-teal-900" to="/dashboard">
        Back to dashboard
      </Link>
    </main>
  );
}
