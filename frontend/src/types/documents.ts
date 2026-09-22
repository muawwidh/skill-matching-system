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
};

export type CandidateJobMatch = {
  id: string;
  candidate_profile_id: string;
  job_id: string;
  score: number;
  matched_required: string[];
  matched_preferred: string[];
  missing_required: string[];
  missing_preferred: string[];
  candidate_skill_count: number;
  job_skill_count: number;
  explanation: string;
  job: Job;
};
