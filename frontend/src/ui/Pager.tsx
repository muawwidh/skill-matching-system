import { ChevronLeft, ChevronRight } from "lucide-react";

import { pageList } from "../utils/coverage";

/** Previous / page numbers / Next. */
export function Pager({ page, pages, onPage, label }: { page: number; pages: number; onPage: (page: number) => void; label: string }) {
  if (pages <= 1) return null;
  const base = "inline-flex h-9 min-w-9 items-center justify-center gap-1 rounded-lg border px-3 text-sm";
  return (
    <nav aria-label={label} className="flex flex-wrap items-center justify-center gap-2">
      <button className={`${base} border-line bg-white text-ink disabled:opacity-40`} disabled={page <= 1} onClick={() => onPage(page - 1)} type="button">
        <ChevronLeft size={16} aria-hidden="true" /> Previous
      </button>
      {pageList(page, pages).map((n, index) =>
        n === null ? (
          <span key={`gap-${index}`} className="px-1 text-muted" aria-hidden="true">…</span>
        ) : (
          <button
            key={n}
            aria-current={n === page ? "page" : undefined}
            aria-label={`Page ${n}`}
            className={`${base} ${n === page ? "border-ink bg-ink text-white" : "border-line bg-white text-ink hover:bg-mist"}`}
            onClick={() => onPage(n)}
            type="button"
          >
            {n}
          </button>
        ),
      )}
      <button className={`${base} border-line bg-white text-ink disabled:opacity-40`} disabled={page >= pages} onClick={() => onPage(page + 1)} type="button">
        Next <ChevronRight size={16} aria-hidden="true" />
      </button>
    </nav>
  );
}
