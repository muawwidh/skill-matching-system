import { Link } from "react-router-dom";

const steps = [
  {
    title: "Add your CV",
    text: "Paste or upload a CV (PDF, Word or plain text). The system reads the text and finds the skills in it.",
  },
  {
    title: "Check your skills",
    text: "Confirm or reject the skills that were found, and add any that are missing. Only skills you confirm are used.",
  },
  {
    title: "See matching jobs",
    text: "Jobs are listed in order of how closely they fit your confirmed skills. For each job you see which required and preferred skills you have and which are missing.",
  },
  {
    title: "Add work experience (optional)",
    text: "Enter job titles and dates to see how many years of related experience you have for a job. This is shown next to the job and never changes the order.",
  },
];

export function AboutPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold text-ink">About</h1>
      <p className="mt-4 leading-7 text-slate-700">
        Skill Gap Job Matching helps you see which jobs fit your skills and which skills you would still need. Skills
        and occupations follow the European ESCO classification.
      </p>
      <ol className="mt-6 space-y-4">
        {steps.map((step, index) => (
          <li key={step.title} className="leading-7 text-slate-700">
            <span className="font-semibold text-ink">
              {index + 1}. {step.title}.
            </span>{" "}
            {step.text}
          </li>
        ))}
      </ol>
      <p className="mt-6 leading-7 text-slate-700">
        This is career guidance, not a hiring decision. Employers do not see your results, and the system does not
        select or reject anyone.
      </p>
      <Link className="mt-6 inline-block font-medium text-ocean hover:text-teal-900" to="/dashboard">
        Back to dashboard
      </Link>
    </main>
  );
}
