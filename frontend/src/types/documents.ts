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
  /** Original posting for live jobs (D053). */
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

export type ProcessingLog = {
  id: string;
  entity_type: string;
  entity_id: string;
  stage: string;
  status: string;
  message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
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

export type JobSkill = CandidateSkill & {
  requirement_type: string;
  /** Detected section of the extracted occurrence; empty for manual skills. */
  source_section?: string;
};

export type CandidateSkillGroup = {
  key: string;
  label: string;
  taxonomy: { concept_id: string; release_id: string; external_id: string;
    preferred_label: string; source: string; version: string } | null;
  occurrences: CandidateSkill[];
};

export type MatchedSkill = {
  label: string;
  matched_via: "taxonomy_concept" | "skill_name";
  /** false: automatically extracted, not reviewed (live jobs, D054). */
  reviewed?: boolean;
};

/** Not matched, but shares a direct ESCO broader skill/knowledge concept with a CV skill (D050). */
export type PartialSkill = { label: string; broader_concept: string; candidate_skill: string; reviewed?: boolean };

export type MissingSkill = {
  label: string;
  /** "skill_name": the job skill has no approved taxonomy link, so it was looked for by name only. */
  checked_via: "taxonomy_concept" | "skill_name";
  /** false: automatically extracted, not reviewed (live jobs, D054). */
  reviewed?: boolean;
};

export type SkillStatusCounts = { approved: number; pending: number; rejected: number };

/** GET /candidates/me/matching-profile: what feeds matching (D041). */
export type MatchingProfile = {
  retrieval_status: RecommendationStatus;
  retrieval_message: string;
  cvs: { id: string; original_filename: string; source: string; processed_at: string | null; skills: SkillStatusCounts }[];
  manual_skills: SkillStatusCounts;
  unattributed_skills: SkillStatusCounts;
};

/** One retrieved job (D045): its retrieval rank, explained by skill coverage. */
export type RecommendationItem = {
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
  job: Job;
};

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
