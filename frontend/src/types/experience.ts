/** Relevant experience (D060). Months are "YYYY-MM"; a null end month means "present". */
export type Occupation = { concept_id: string; label: string; isco_code: string | null; isco_unit_group: string };
/** method "label": matched by wording; "embedding": similar meaning (shown after, D060). */
export type OccupationSuggestion = Occupation & { confidence: number; method?: "label" | "embedding" };

export type WorkEntry = {
  id: string;
  title: string;
  start_month: string;
  end_month: string | null;
  source: "manual" | "cv_detected";
  months: number;
  occupation: Occupation | null;
};

export type WorkEntryPayload = {
  title: string;
  start_month: string;
  end_month: string | null;
  occupation_concept_id: string | null;
  source: "manual" | "cv_detected";
};

export type DetectedWorkEntry = { title: string; start_month: string; end_month: string | null; month_precision: boolean };
