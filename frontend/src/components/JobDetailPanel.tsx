import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import { getJobMatch } from "../api/documents";
import type { RecommendationItem } from "../types/documents";
import { ExperienceBadge, RankBadge } from "../ui/Badges";
import { Chip } from "../ui/Chip";
import { SkillBar } from "../ui/CoverageBar";
import { Tip } from "../ui/Tip";
import { coverageView, languageLabel, locationText, NO_REQUIRED_NOTE, NO_SKILLS_LABEL, postedAgo } from "../utils/coverage";
import { AUTOMATIC_TOOLTIP, isLiveJobSource } from "../utils/reviewStatus";
import { fraction, jobMapNodes, previewCoverage } from "../utils/skillMap";
import { SkillMap } from "./SkillMap";

export const UNREVIEWED = "automatically extracted, not reviewed";

/** Job languages against the candidate's confirmed languages (by name). Not counted in the skill coverage. */
export function LanguageChips({ item }: { item: RecommendationItem }) {
  const languages = item.languages;
  const label = languageLabel(languages);
  if (!languages || !label) return null;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      {languages.matched.map((entry) => <Chip key={`m-${entry.label}`} kind="matched">{entry.label}</Chip>)}
      {languages.missing.map((entry) => <Chip key={`x-${entry.label}`} kind="missing">{entry.label}</Chip>)}
    </span>
  );
}

export function jobMeta(item: RecommendationItem): string {
  return [item.job.company, locationText(item), postedAgo(item.job.posted_at)].filter(Boolean).join(" · ");
}

/** Explanation lines, without the not-assessed lists (shown on their own line). */
function explanationLines(text: string): string[] {
  return text.split("\n").filter((line) => line && !/^Also (required|preferred) — not assessed/.test(line));
}

function Line({ term, children, tip }: { term: string; children: ReactNode; tip?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5">
      <dt className="eyebrow w-24 shrink-0">{term}</dt>
      <dd className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5 text-sm text-ink">
        {children}
        {tip ? <Tip label={`About ${term.toLowerCase()}`} align="right">{tip}</Tip> : null}
      </dd>
    </div>
  );
}

function experienceTip(item: RecommendationItem): ReactNode {
  const related = item.related_experience;
  const occupation = item.job_occupation;
  return (
    <>
      {related ? (
        <span className="block">
          About {related.relevant_years} year{related.relevant_years === 1 ? "" : "s"} in related roles
          ({related.isco_group_label || `ISCO ${related.isco_group}`}); the job asks {related.min_required_years}+.
        </span>
      ) : null}
      {occupation ? (
        <span className="block">
          {occupation.determined ? `Occupation: ${occupation.label}${occupation.isco_unit_group ? ` · ${occupation.isco_unit_group}` : ""}` : "Occupation not determined"}
        </span>
      ) : null}
      <span className="mt-1 block text-muted">Shown for information; never changes the order.</span>
    </>
  );
}

export function JobDetailPanel({ item, rankTotal, extra, accessToken, preview }: {
  item: RecommendationItem; rankTotal: number; extra?: ReactNode; accessToken?: string; preview?: string | null;
}) {
  const job = item.job;
  const live = isLiveJobSource(job.source);
  const view = coverageView(item);
  // The candidate's skills this job does not ask for come from the job detail request.
  const detail = useQuery({
    queryKey: ["recommendations", "job", item.job_id],
    queryFn: () => getJobMatch(accessToken as string, item.job_id),
    enabled: Boolean(accessToken),
  });
  const nodes = jobMapNodes({ ...item, not_needed: detail.data?.not_needed ?? [] });
  const shown = previewCoverage(item, preview ?? null);
  const notAssessed = [...(item.not_assessed_required ?? []), ...(item.not_assessed_preferred ?? [])];
  const meta = jobMeta(item);
  const basisText = view.basis === "required" ? "required skills" : view.basis === "mentioned" ? "skills mentioned in the ad" : null;

  return (
    <article className="card space-y-5" aria-labelledby="job-detail-title">
      <header key={item.job_id} className="flex animate-rise items-start gap-4">
        <RankBadge rank={item.rank} large />
        <div className="min-w-0 flex-1">
          <p className="eyebrow">#{item.rank} of {rankTotal}</p>
          <h2 id="job-detail-title" className="mt-0.5 text-2xl font-semibold leading-tight text-ink">{job.title}</h2>
          {meta ? <p className="mt-1 text-sm text-muted">{meta}</p> : null}
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {job.external_url ? (
              <a className="btn-primary" href={job.external_url} rel="noopener noreferrer" target="_blank">
                Original posting <ExternalLink size={15} aria-hidden="true" />
              </a>
            ) : null}
            {live ? (
              <Tip label="About automatic skills" text="automatic skills" align="left">
                {AUTOMATIC_TOOLTIP}. Taken from the posting text; may be incomplete or wrong.
              </Tip>
            ) : null}
            {job.attribution ? (
              <a className="text-xs text-muted underline underline-offset-4 hover:text-ink" href={job.attribution.url} rel="noopener noreferrer" target="_blank">
                via {job.attribution.name}
              </a>
            ) : null}
          </div>
        </div>
      </header>

      <section aria-label="Skill coverage" className="space-y-2">
        <div className="flex items-baseline justify-between gap-3">
          <p className="numeral text-3xl text-ink">
            {view.basis === "none" ? "—" : fraction(shown.counts, shown.closes)}
            {basisText ? <span className="ml-2 font-sans text-sm font-normal tracking-normal text-muted">{basisText}</span> : null}
          </p>
          {view.basis === "mentioned" ? <Tip label="About mentioned skills" align="right">{NO_REQUIRED_NOTE}.</Tip> : null}
        </div>
        <SkillBar counts={shown.counts} closes={shown.closes} label={view.label} />
        {view.basis === "none" ? <p className="text-sm text-muted">{NO_SKILLS_LABEL}</p> : null}
      </section>

      {nodes.length ? (
        <section aria-labelledby="skill-map-heading" className="space-y-2">
          <h3 id="skill-map-heading" className="eyebrow flex items-center gap-1.5">
            Skill map
            <Tip label="About the skill map" align="left">
              Grouped by ESCO skill area. Hover or focus a skill for how it was compared. Related: you have a skill in the same
              narrow ESCO area. Not needed: in your profile, not asked for by this job.
            </Tip>
          </h3>
          <SkillMap nodes={nodes} glow={preview} />
        </section>
      ) : null}

      <dl className="divide-y divide-line border-y border-line">
        <Line term="Experience" tip={experienceTip(item)}>
          <ExperienceBadge item={item} />
        </Line>
        {item.languages?.compared ? (
          <Line term="Languages" tip="Compared by name with the languages on My profile; levels are not compared. Not part of the skill counts or the order.">
            <span className="numeral">{item.languages.matched.length}/{item.languages.matched.length + item.languages.missing.length}</span>
            <LanguageChips item={item} />
          </Line>
        ) : item.languages?.note ? (
          <Line term="Languages" tip={item.languages.note}><span className="text-muted">not compared</span></Line>
        ) : null}
        <Line term="Not assessed" tip="Qualifications, experience and certifications listed in the posting; the system does not check them.">
          <span className={notAssessed.length ? "" : "text-muted"}>{notAssessed.length ? notAssessed.join(", ") : "—"}</span>
        </Line>
      </dl>

      <details className="group text-sm">
        <summary className="cursor-pointer font-medium text-ink">Explanation</summary>
        <ul className="mt-2 space-y-1 text-muted">
          {explanationLines(item.explanation).map((line) => <li key={line}>{line}</li>)}
        </ul>
      </details>
      {extra}
    </article>
  );
}
