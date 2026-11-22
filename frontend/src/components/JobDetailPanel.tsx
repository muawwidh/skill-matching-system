import { BriefcaseBusiness, ExternalLink, Info } from "lucide-react";
import type { ReactNode } from "react";

import type { MatchedSkill, MissingSkill, PartialSkill, RecommendationItem } from "../types/documents";
import { ExperienceBadge, RankBadge } from "../ui/Badges";
import { CoverageBar } from "../ui/CoverageBar";
import { postedAgo, requiredCounts } from "../utils/coverage";
import { isLiveJobSource } from "../utils/reviewStatus";

export const UNREVIEWED = "automatically extracted, not reviewed";

export function jobMeta(item: RecommendationItem): string {
  return [item.job.company, item.job.location, postedAgo(item.job.posted_at)].filter(Boolean).join(" · ");
}

function Tag({ tone, children }: { tone: "required" | "preferred"; children: ReactNode }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone === "required" ? "bg-night text-white" : "bg-neutral-bg text-neutral-text"}`}>
      {children}
    </span>
  );
}

function Row({ symbol, symbolClass, label, tag, detail, unreviewed }: {
  symbol: string; symbolClass: string; label: string; tag: "required" | "preferred"; detail: ReactNode; unreviewed?: boolean;
}) {
  return (
    <li className="flex gap-3 py-2.5">
      <span aria-hidden="true" className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${symbolClass}`}>{symbol}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-ink">{label}</span>
          <Tag tone={tag}>{tag}</Tag>
        </div>
        <p className="mt-0.5 text-xs text-muted">
          {detail}
          {unreviewed ? ` · ${UNREVIEWED}` : ""}
        </p>
      </div>
    </li>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <section className="border-t border-line pt-4">
      <h3 className="text-sm font-semibold text-ink">
        {title}
        {count !== undefined ? <span className="ml-1.5 font-normal text-muted">({count})</span> : null}
      </h3>
      {children}
    </section>
  );
}

const withTag = <T,>(required: T[], preferred: T[]) => [
  ...required.map((item) => ({ item, tag: "required" as const })),
  ...preferred.map((item) => ({ item, tag: "preferred" as const })),
];

const MATCHED_VIA: Record<MatchedSkill["matched_via"], string> = {
  taxonomy_concept: "Matched by ESCO concept",
  skill_name: "Matched by the same skill name",
};
const CHECKED_VIA: Record<MissingSkill["checked_via"], string> = {
  taxonomy_concept: "Not found in your profile by ESCO concept or name",
  skill_name: "Not found by name; it may be in your CV under a different wording",
};

/** Explanation lines, without the not-assessed lists (shown in their own section). */
function explanationLines(text: string): string[] {
  return text.split("\n").filter((line) => line && !/^Also (required|preferred) — not assessed/.test(line));
}

function ExperienceLine({ item }: { item: RecommendationItem }) {
  const related = item.related_experience;
  const occupation = item.job_occupation;
  return (
    <div className="space-y-1.5 text-sm">
      <ExperienceBadge item={item} />
      {related ? (
        <p className="text-ink">
          About {related.relevant_years} year{related.relevant_years === 1 ? "" : "s"} in related roles ({related.isco_group_label || `ISCO ${related.isco_group}`});
          the job asks {related.min_required_years}+ years.
        </p>
      ) : null}
      {occupation ? (
        <p className="flex items-start gap-1.5 text-xs text-muted" title="ESCO occupation linked automatically from the job title">
          <BriefcaseBusiness size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          {occupation.determined ? `Occupation: ${occupation.label}${occupation.isco_unit_group ? ` · ${occupation.isco_unit_group}` : ""}` : "Occupation not determined"}
        </p>
      ) : null}
      <p className="text-xs text-muted">Experience is shown for information; it never changes the ranking.</p>
    </div>
  );
}

export function JobDetailPanel({ item, rankTotal, extra }: { item: RecommendationItem; rankTotal: number; extra?: ReactNode }) {
  const job = item.job;
  const live = isLiveJobSource(job.source);
  const have = withTag<MatchedSkill>(item.matched_required, item.matched_preferred);
  const related = withTag<PartialSkill>(item.partial_required, item.partial_preferred);
  const develop = withTag<MissingSkill>(item.missing_required, item.missing_preferred);
  const notRequired = item.not_assessed_required ?? [];
  const notPreferred = item.not_assessed_preferred ?? [];
  const meta = jobMeta(item);

  return (
    <article className="card space-y-5" aria-labelledby="job-detail-title">
      <div className="flex items-start gap-3">
        <RankBadge rank={item.rank} large />
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted" title="Position among the jobs found for your profile, closest in meaning first. Skill coverage explains the job; it does not change the order.">
            #{item.rank} of {rankTotal}
          </p>
          <h2 id="job-detail-title" className="text-2xl font-semibold leading-tight text-ink">{job.title}</h2>
          {meta ? <p className="mt-1 text-sm text-muted">{meta}</p> : null}
          {job.attribution ? (
            <p className="mt-0.5 text-xs text-muted">
              Source:{" "}
              <a className="link" href={job.attribution.url} rel="noopener noreferrer" target="_blank">{job.attribution.name}</a>
            </p>
          ) : null}
        </div>
      </div>

      <CoverageBar counts={requiredCounts(item)} />

      <div className="rounded-xl bg-teal-soft p-4 text-sm text-teal-text">
        <h3 className="mb-1.5 font-semibold">Why this job</h3>
        <ul className="space-y-1">
          {explanationLines(item.explanation).map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>

      <Section title="Skills you have" count={have.length}>
        {have.length ? (
          <ul className="divide-y divide-line">
            {have.map(({ item: skill, tag }) => (
              <Row key={`${tag}-${skill.label}`} symbol="✓" symbolClass="bg-teal-soft text-teal-text" label={skill.label} tag={tag}
                detail={MATCHED_VIA[skill.matched_via]} unreviewed={skill.reviewed === false} />
            ))}
          </ul>
        ) : <p className="mt-2 text-sm text-muted">None of the listed skills yet.</p>}
      </Section>

      {related.length ? (
        <Section title="Related skill in your profile" count={related.length}>
          <ul className="divide-y divide-line">
            {related.map(({ item: skill, tag }) => (
              <Row key={`${tag}-${skill.label}`} symbol="~" symbolClass="bg-caution-bg text-caution-text" label={skill.label} tag={tag}
                detail={`Not in your CV, but related: you have ${skill.candidate_skill} (same ESCO area: ${skill.broader_concept})`}
                unreviewed={skill.reviewed === false} />
            ))}
          </ul>
        </Section>
      ) : null}

      <Section title="Skills to develop" count={develop.length}>
        {develop.length ? (
          <ul className="divide-y divide-line">
            {develop.map(({ item: skill, tag }) => (
              <Row key={`${tag}-${skill.label}`} symbol="○" symbolClass="bg-miss-bg text-miss-text" label={skill.label} tag={tag}
                detail={CHECKED_VIA[skill.checked_via]} unreviewed={skill.reviewed === false} />
            ))}
          </ul>
        ) : <p className="mt-2 text-sm text-muted">You have every listed skill.</p>}
      </Section>

      <Section title="Experience">
        <div className="mt-2"><ExperienceLine item={item} /></div>
      </Section>

      <Section title="Also required — not assessed">
        {notRequired.length || notPreferred.length ? (
          <div className="mt-2 space-y-2 text-sm">
            {notRequired.length ? <p className="text-ink">{notRequired.join(", ")}</p> : null}
            {notPreferred.length ? (
              <p className="text-muted"><span className="font-medium text-ink">Also preferred — not assessed:</span> {notPreferred.join(", ")}</p>
            ) : null}
            <p className="text-xs text-muted">Qualifications, experience and certifications listed in the posting; the system does not check them.</p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted">
            Other requirements in the posting (for example a degree or languages) are not assessed; check the original posting.
          </p>
        )}
      </Section>

      {job.external_url ? (
        <a className="btn-primary w-full" href={job.external_url} rel="noopener noreferrer" target="_blank">
          View original posting <ExternalLink size={16} aria-hidden="true" />
        </a>
      ) : null}

      {live ? (
        <p className="flex gap-2 text-xs text-muted">
          <Info size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          Skills of this job were {UNREVIEWED}: they come from the posting text and may be incomplete or wrong.
        </p>
      ) : null}
      {extra}
    </article>
  );
}
