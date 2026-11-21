/** Sources that are not live job feeds (backend NON_LIVE_SOURCES, D052). */
const NON_LIVE_JOB_SOURCES = new Set(["manual", "evaluation"]);

export const AUTOMATIC_TOOLTIP = "Automatic: extracted from the live job posting, not reviewed by staff";
export const AUTOMATIC_LINK_TOOLTIP = "Automatic: suggested for a live job posting, not reviewed by staff";

export function isLiveJobSource(source: string | null | undefined): boolean {
  return Boolean(source) && !NON_LIVE_JOB_SOURCES.has(source as string);
}

/**
 * Display label for a review status. Live-job skills and link suggestions are rarely
 * reviewed, so their "pending" items read "automatic" (wording only, D054).
 */
export function reviewStatusLabel(status: string, liveJob = false): string {
  return liveJob && status === "pending" ? "automatic" : status;
}
