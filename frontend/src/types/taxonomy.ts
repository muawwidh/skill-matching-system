export type TaxonomyVersion = {
  id: string;
  version: string;
  release_date: string;
  import_filename: string;
  status: string;
  is_sample: boolean;
  imported_at: string;
  source_code: string;
  source_name: string;
};

export type TaxonomyConcept = {
  id: string;
  external_id: string;
  preferred_label: string;
  description: string;
  concept_type: string;
  language: string;
  source_code: string;
  taxonomy_version: string;
  alternative_labels: string[];
};

export type TaxonomyLinkCandidate = {
  id: string;
  term_source: "candidate" | "job";
  extracted_term_id: string;
  raw_text: string;
  normalized_text: string;
  match_method: string;
  confidence_score: number;
  rank: number;
  review_status: string;
  concept: TaxonomyConcept;
};

export type EscoOnetMapping = {
  id: string;
  esco_concept_id: string;
  esco_label: string;
  onet_occupation_id: string;
  onet_code: string;
  onet_title: string;
  mapping_type: string;
  confidence_score: number;
  source: string;
  version: string;
};

export type TaxonomyImportResult = {
  source_code: string;
  version: string;
  concepts_imported: number;
  occupations_imported: number;
  mappings_imported: number;
  is_sample: boolean;
};

export type TaxonomyReviewGroup = {
  term_source: "candidate" | "job";
  extracted_term_id: string;
  raw_text: string;
  inconsistent: boolean;
  selection: { candidate_id: string | null; concept: TaxonomyConcept; token: string } | null;
  candidates: TaxonomyLinkCandidate[];
};

export type TaxonomyReviewEvent = {
  id: string;
  candidate_id: string;
  action: string;
  reviewer_id: string | null;
  created_at: string;
  before_state: ReviewSnapshot;
  after_state: ReviewSnapshot;
};

type ReviewSnapshot = {
  selection: { candidate_id: string | null; label: string } | null;
  candidates: { id: string; label: string; status: string }[];
};
