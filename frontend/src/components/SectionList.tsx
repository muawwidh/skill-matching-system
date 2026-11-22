import type { Section } from "../types/documents";

export function SectionList({ sections }: { sections: Section[] }) {
  if (sections.length === 0) {
    return <p className="text-sm text-muted">No sections detected yet.</p>;
  }

  return (
    <div className="space-y-3">
      {sections.map((section) => (
        <article key={section.id} className="rounded-lg border border-line bg-mist p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-lg bg-ocean px-2 py-1 text-xs font-medium text-white">
              {section.section_type.replace(/_/g, " ")}
            </span>
            <h3 className="text-sm font-semibold text-ink">{section.heading}</h3>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink">
            {section.content}
          </p>
        </article>
      ))}
    </div>
  );
}
