export type Section = {
  id: string;
  section_type: string;
  heading: string;
  content: string;
  start_char: number;
  end_char: number;
  confidence_score: number;
  extraction_method: string;
};

export type CvDocument = {
  id: string;
  original_filename: string;
  content_type: string;
  source: string;
  status: string;
  raw_text: string;
  cleaned_text: string;
  size_bytes: number;
  error_message: string;
  processed_at: string | null;
  sections: Section[];
};

export type Job = {
  id: string;
  title: string;
  company: string;
  location: string;
  employment_type: string;
  description: string;
  cleaned_description: string;
  status: string;
  source: string;
  error_message: string;
  processed_at: string | null;
  /** Original posting for live jobs. */
  external_url: string;
  posted_at: string | null;
  last_seen_at: string | null;
  attribution: { name: string; url: string } | null;
  sections: Section[];
};

export type JobPayload = {
  title: string;
  company: string;
  location: string;
  employment_type: string;
  description: string;
};

export type CandidateSkill = {
  id: string;
  raw_text: string;
  normalized_text: string;
  skill_type: string;
  evidence_sentence: string;
  confidence_score: number;
  review_status: string;
  source: string;
};

/** A language on My profile; origin: added (by hand), cv (found in a CV), skill_editor (typed as a skill earlier). */
export type ProfileLanguage = {
  id: string;
  label: string;
  name: string;
  level: string | null;
  status: string;
  origin: "added" | "cv" | "skill_editor";
  evidence: string;
};

export const LANGUAGE_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "native"] as const;

/** Job languages against the candidate's confirmed languages, by name only; never part of skill counts or order. */
export type LanguageCoverage = {
  compared: boolean;
  matched: { label: string; requirement: string; reviewed: boolean }[];
  missing: { label: string; requirement: string; reviewed: boolean }[];
  note: string;
};

export type JobSkill = CandidateSkill & {
  requirement_type: string;
  /** Detected section of the extracted occurrence; empty for manual skills. */
  source_section?: string;
};

/** An ESCO skill group just below the top level (e.g. "06" ICT, "S4" management skills). Display only. */
export type EscoArea = { code: string; label: string };

/** A skill added by hand, with its ESCO area when linked. */
export type ManualSkill = CandidateSkill & { esco_area?: EscoArea | null };

export type CandidateSkillGroup = {
  key: string;
  label: string;
  esco_area?: EscoArea | null;
  taxonomy: { concept_id: string; release_id: string; external_id: string;
    preferred_label: string; source: string; version: string } | null;
  occurrences: CandidateSkill[];
};

export type MatchedSkill = {
  label: string;
  matched_via: "taxonomy_concept" | "skill_name";
  /** false: automatically extracted, not reviewed (live jobs). */
  reviewed?: boolean;
  esco_area?: EscoArea | null;
};

/** Not matched, but shares a direct ESCO broader skill/knowledge concept with a CV skill. */
export type PartialSkill = { label: string; broader_concept: string; candidate_skill: string; reviewed?: boolean; esco_area?: EscoArea | null };

export type MissingSkill = {
  label: string;
  /** "skill_name": the job skill has no approved taxonomy link, so it was looked for by name only. */
  checked_via: "taxonomy_concept" | "skill_name";
  /** false: automatically extracted, not reviewed (live jobs). */
  reviewed?: boolean;
  esco_area?: EscoArea | null;
};

export type SkillStatusCounts = { approved: number; pending: number; rejected: number };

/** GET /candidates/me/matching-profile: what feeds matching. */
export type MatchingProfile = {
  retrieval_status: RecommendationStatus;
  retrieval_message: string;
  cvs: { id: string; original_filename: string; source: string; processed_at: string | null; skills: SkillStatusCounts }[];
  manual_skills: SkillStatusCounts;
  unattributed_skills: SkillStatusCounts;
};

/** One retrieved job: its retrieval rank, explained by skill coverage. */
/** The job title's ESCO occupation; determined false = "occupation not determined". */
export type JobOccupation = {
  determined: boolean;
  concept_id: string | null;
  label: string | null;
  isco_code: string | null;
  isco_unit_group: string;
};

/** Related experience for one job: explanation only, never part of the order. */
export type RelatedExperience = {
  relevant_months: number;
  relevant_years: number;
  isco_group: string;
  isco_group_label: string;
  min_required_years: number;
  meets_requirement: boolean;
};

export type RecommendationItem = {
  job_occupation?: JobOccupation | null;
  related_experience?: RelatedExperience | null;
  rank: number;
  job_id: string;
  matched_required: MatchedSkill[];
  matched_preferred: MatchedSkill[];
  missing_required: MissingSkill[];
  missing_preferred: MissingSkill[];
  partial_required: PartialSkill[];
  partial_preferred: PartialSkill[];
  candidate_skill_count: number;
  job_skill_count: number;
  explanation: string;
  /** Job terms of other kinds (qualification, experience, certification): listed, not assessed. */
  not_assessed_required?: string[];
  not_assessed_preferred?: string[];
  languages?: LanguageCoverage;
  /** required | mentioned (no skill marked required: all mentioned skills) | none (no skills identified). */
  coverage_basis?: "required" | "mentioned" | "none";
  /** Same posting in several locations, shown as one card. */
  locations?: string[];
  duplicate_job_ids?: string[];
  /** Minimum years the job text asks for; null when none is stated. */
  min_required_years?: number | null;
  job: Job;
};

/** GET /matches/jobs/{id}: one job's coverage, plus the candidate's skills this job does not ask for. */
export type JobMatch = Omit<RecommendationItem, "rank"> & { not_needed?: { label: string; esco_area?: EscoArea | null }[] };

/** GET /matches/skill-gaps: most frequent required missing skills across the top results. */
export type SkillGaps = { status: RecommendationStatus; of: number; gaps: { label: string; missing_in: number }[] };

/** GET /matches/job-pool: live jobs searched and the last successful import. */
export type JobPool = { live_jobs: number; last_import_at: string | null };

export type RecommendationStatus =
  | "ready"
  | "profile_not_ready"
  | "no_approved_skills"
  | "profile_not_indexed"
  | "retrieval_unavailable";

export type RecommendationList = {
  status: RecommendationStatus;
  message: string;
  top_n: number;
  /** Retrieved jobs (at most top_n); `results` is one page of them. */
  total: number;
  page: number;
  page_size: number;
  active_jobs: number;
  unindexed_jobs: number;
  /** Related-experience filter. */
  hide_below_experience?: boolean;
  hidden_by_experience?: number;
  /** Further postings of the same job in other locations folded into one card. */
  collapsed_duplicates?: number;
  has_work_entries_with_occupation?: boolean;
  results: RecommendationItem[];
};

// Administrator system overview (GET /admin/overview). Read-only counts.
export type ReviewCounts = { approved: number; pending: number; rejected: number; total: number };
export type LinkCoverage = { approved_skills: number; approved_link: number; pending_link: number; no_link: number };
export type IndexCoverage = { eligible: number; indexed: number | null };

export type SystemOverview = {
  generated_at: string;
  taxonomy: {
    releases: {
      source: string;
      version: string;
      status: string;
      is_sample: boolean;
      skills: number;
      occupations: number;
      other: number;
      by_type: Record<string, number>;
    }[];
    esco_onet_mappings_total: number;
    esco_onet_mappings: { esco_version: string; onet_version: string; rows: number }[];
  };
  candidates: { accounts: number; cvs: { uploaded: number; processed: number; failed: number; failed_note: string } };
  jobs: { total: number; active: number; archived: number };
  skills: {
    cv_extracted: ReviewCounts;
    cv_added_manually: ReviewCounts;
    job_extracted: ReviewCounts;
    /** job_extracted split by job group: manual, evaluation, live. */
    job_by_source?: Partial<Record<"manual" | "evaluation" | "live", ReviewCounts>>;
  };
  taxonomy_links: { cv: LinkCoverage; job: LinkCoverage };
  retrieval_index: {
    model_id: string;
    model_revision: string;
    template_version: string;
    profiles: IndexCoverage;
    jobs: IndexCoverage;
    note: string;
  };
};
