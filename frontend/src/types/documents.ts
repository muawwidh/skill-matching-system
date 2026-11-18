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
};

export type MissingSkill = {
  label: string;
  /** "skill_name": the job skill has no approved taxonomy link, so it was looked for by name only. */
  checked_via: "taxonomy_concept" | "skill_name";
};

// The API also returns a legacy `score` column; it is intentionally not typed here so it cannot be displayed.
export type CandidateJobMatch = {
  id: string;
  candidate_profile_id: string;
  job_id: string;
  matched_required: MatchedSkill[];
  matched_preferred: MatchedSkill[];
  missing_required: MissingSkill[];
  missing_preferred: MissingSkill[];
  candidate_skill_count: number;
  job_skill_count: number;
  explanation: string;
  job: Job;
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
  skills: { cv_extracted: ReviewCounts; cv_added_manually: ReviewCounts; job_extracted: ReviewCounts };
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
