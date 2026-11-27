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

/** Explanations kept off the working pages (they show headings, numbers and actions only). */
const reading = [
  ["Order", "Matches are ranked by how similar a job is to your profile. Skill coverage explains each job and never changes the order. Your position numbers count only the jobs shown."],
  ["X/Y and the bar", "One segment per skill the job asks for: green you have it, violet a related skill is in your profile, orange a gap. Required skills are counted; when an ad marks none as required, every skill it mentions is counted instead. If no skills could be identified, see the original ad."],
  ["Skill map", "The selected job's skills and yours, grouped by ESCO skill area. Outlined skills are in your profile but not asked for by this job. Bold skills are required."],
  ["Related", "You do not have the job's skill, but you have one in the same narrow ESCO area (a direct broader skill they share)."],
  ["What if I learned", "The most frequent gaps on the page. Selecting one previews how many of the shown jobs it would close a gap in. Nothing is saved and the order does not change."],
  ["Automatic skills", "Skills of jobs collected from job sites are extracted automatically and not reviewed; they may be incomplete or wrong."],
  ["Experience", "Your years in roles of the same occupation group compared with the minimum the ad states. You can hide jobs above your experience; jobs without a stated minimum are never hidden."],
  ["Languages", "Compared by name with the languages on your profile; levels are not compared. Not part of the skill counts or the order."],
  ["Not assessed", "Degrees, certifications and other requirements are listed but not checked."],
  ["Repeated postings", "The same posting published for several locations is shown once, with all its locations."],
];

export function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section className="card animate-rise p-8">
        <h1 className="text-4xl font-semibold tracking-tight text-ink">About SkillGap</h1>
        <p className="mt-4 leading-7 text-ink">
          SkillGap helps you see which jobs fit your skills and which skills you would still need. Skills
          and occupations follow the European ESCO classification.
        </p>
        <ol className="mt-6 space-y-4">
          {steps.map((step, index) => (
            <li key={step.title} className="leading-7 text-ink">
              <span className="font-semibold text-ink">
                {index + 1}. {step.title}.
              </span>{" "}
              {step.text}
            </li>
          ))}
        </ol>
        <p className="mt-6 leading-7 text-ink">
          This is career guidance, not a hiring decision. Employers do not see your results, and the system does not
          select or reject anyone.
        </p>
      </section>
      <section className="card animate-rise p-8" aria-labelledby="reading-heading" style={{ animationDelay: "60ms" }}>
        <h2 id="reading-heading" className="text-2xl font-semibold text-ink">Reading your matches</h2>
        <dl className="mt-5 space-y-4">
          {reading.map(([term, text]) => (
            <div key={term}>
              <dt className="font-semibold text-ink">{term}</dt>
              <dd className="mt-1 leading-7 text-ink">{text}</dd>
            </div>
          ))}
        </dl>
        <Link className="mt-6 inline-block link" to="/dashboard">Back to dashboard</Link>
      </section>
    </div>
  );
}
