/** Relevant experience. Months are "YYYY-MM"; a null end month means "present". */
export type Occupation = { concept_id: string; label: string; isco_code: string | null; isco_unit_group: string };
/** method "label": matched by wording; "embedding": similar meaning (shown after). */
export type OccupationSuggestion = Occupation & { confidence: number; method?: "label" | "embedding" };

export type WorkEntry = {
  id: string;
  title: string;
  start_month: string;
  end_month: string | null;
  source: "manual" | "cv_detected";
  /** The CV a "cv_detected" entry was taken from; null for manual entries. */
  source_cv_id: string | null;
  months: number;
  occupation: Occupation | null;
};

export type WorkEntryPayload = {
  title: string;
  start_month: string;
  end_month: string | null;
  occupation_concept_id: string | null;
  source: "manual" | "cv_detected";
  source_cv_id?: string | null;
};

export type DetectedWorkEntry = {
  title: string;
  /** Offered when the title is uncertain ("" title); never company lines. */
  title_choices?: string[];
  cv_id: string;
  start_month: string;
  end_month: string | null;
  month_precision: boolean;
};
