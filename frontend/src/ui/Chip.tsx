import { X } from "lucide-react";
import type { ReactNode } from "react";

export type ChipKind = "matched" | "related" | "missing" | "review" | "neutral" | "teal";

const STYLE: Record<ChipKind, string> = {
  matched: "bg-teal-soft text-teal-text",
  related: "bg-caution-bg text-caution-text",
  missing: "bg-miss-bg text-miss-text",
  review: "border border-dashed border-caution-line bg-caution-bg text-caution-text",
  neutral: "bg-neutral-bg text-neutral-text",
  teal: "bg-teal-soft text-teal-text",
};

const SYMBOL: Partial<Record<ChipKind, string>> = { matched: "✓", related: "~", missing: "○" };

/** Rounded pill with a leading symbol (✓ matched, ~ related, ○ missing). The symbol is decorative. */
export function Chip({ kind, title, dashed, children, onRemove, removeLabel }: {
  kind: ChipKind; title?: string; dashed?: boolean; children: ReactNode; onRemove?: () => void; removeLabel?: string;
}) {
  const symbol = SYMBOL[kind];
  return (
    <span
      className={`inline-flex max-w-full items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${STYLE[kind]}${dashed ? " border border-dashed border-current" : ""}`}
      title={title}
    >
      {symbol ? <span aria-hidden="true">{symbol}</span> : null}
      <span className="truncate">{children}</span>
      {onRemove ? (
        <button aria-label={removeLabel ?? "Remove"} className="-mr-1 ml-0.5 grid h-5 w-5 place-items-center rounded-full hover:bg-black/10" onClick={onRemove} type="button">
          <X size={12} aria-hidden="true" />
        </button>
      ) : null}
    </span>
  );
}
