export function ReviewSummary({ rows, unlinked }: {
  rows: { review_status: string; evidence_sentence?: string; requirement_type?: string }[];
  unlinked?: number;
}) {
  const count = (status: string) => rows.filter(row => row.review_status === status).length;
  return <div className="review-summary" aria-label="Saved extraction review summary">
    <p>{rows.length} occurrences · {count("approved")} approved · {count("pending")} pending · {count("rejected")} rejected</p>
    <p>{rows.filter(row => !row.evidence_sentence?.trim()).length} without evidence text
      {rows.some(row => row.requirement_type !== undefined) && ` · ${rows.filter(row => row.requirement_type === "unknown").length} unknown requirement classifications`}
      {unlinked !== undefined && ` · ${unlinked} unlinked occurrences`}</p>
    <p className="match-muted">Saved state only. Confidence and taxonomy links do not confirm evidence. Unlinked does not mean incorrect; no pending rows does not prove completeness.</p>
  </div>;
}
