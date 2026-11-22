import { Link } from "react-router-dom";

const sections = [
  {
    title: "Your consent",
    text: "A CV is processed only after you tick the consent box. You can delete it at any time.",
  },
  {
    title: "What is stored",
    text: "Your name, e-mail address and a protected form of your password; the text of your CVs (the uploaded file itself is not kept); the skills found and your decisions on them; work entries you add (job title, months and an occupation, never the employer); and your settings on the Jobs page.",
  },
  {
    title: "What is used for matching",
    text: "Only the skills you have confirmed. Age, gender, religion, nationality, marital status, photographs and other personal characteristics are not used.",
  },
  {
    title: "Who sees your results",
    text: "Your job matches and work entries are visible to you only. Administrators see totals across all users, never one person's results. Staff who check how skill words are linked to ESCO may see single skill words found in CVs, without your name or the CV text.",
  },
  {
    title: "Deleting your data",
    text: "You can delete a CV on the CVs page; the skills found in it go with it, and so do the work entries taken from it unless you choose to keep them. Work entries you typed in yourself stay until you delete them. You can delete your account and all your data on the Dashboard. Backups made before a deletion keep the data until they are replaced.",
  },
  {
    title: "Job postings",
    text: "Jobs collected from public job sites are stored with e-mail addresses, phone numbers and contact names removed, together with a link to the original posting.",
  },
  {
    title: "Guidance, not hiring",
    text: "The results support your own career decisions. They are not shared with employers and are not used to select or reject candidates.",
  },
];

export function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold text-ink">Privacy</h1>
      <dl className="mt-6 space-y-5">
        {sections.map((section) => (
          <div key={section.title}>
            <dt className="font-semibold text-ink">{section.title}</dt>
            <dd className="mt-1 leading-7 text-slate-700">{section.text}</dd>
          </div>
        ))}
      </dl>
      <Link className="mt-6 inline-block font-medium text-ocean hover:text-teal-900" to="/dashboard">
        Back to dashboard
      </Link>
    </main>
  );
}
