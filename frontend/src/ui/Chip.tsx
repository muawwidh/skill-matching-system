import { X } from "lucide-react";
import type { ReactNode } from "react";

export type ChipKind = "matched" | "related" | "missing" | "review" | "neutral" | "teal" | "idle" | "preview";

/** Colour carries meaning only: have (green), related (violet, dashed), gap (orange), not needed (outline). */
const STYLE: Record<ChipKind, string> = {
  matched: "border border-have/25 bg-have-bg text-have-text",
  teal: "border border-have/25 bg-have-bg text-have-text",
  related: "border border-dashed border-related bg-related-bg text-related-text",
  missing: "border border-gap/30 bg-gap-bg text-gap-text",
  preview: "border border-gap bg-gap text-white",
  review: "border border-dashed border-idle bg-white text-idle-text",
  idle: "border border-idle bg-white text-idle-text",
  neutral: "border border-line bg-mist text-idle-text",
};

/** Rounded pill. An optional remove button is a real button with its own label. */
export function Chip({ kind, title, dashed, children, onRemove, removeLabel, onClick, pressed, className = "" }: {
  kind: ChipKind; title?: string; dashed?: boolean; children: ReactNode; onRemove?: () => void; removeLabel?: string;
  onClick?: () => void; pressed?: boolean; className?: string;
}) {
  const style = `inline-flex max-w-full items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors duration-300 ${STYLE[kind]}${dashed ? " border-dashed" : ""} ${className}`;
  if (onClick) {
    return (
      <button aria-pressed={pressed} className={`${style} lift`} onClick={onClick} title={title} type="button">
        <span className="truncate">{children}</span>
      </button>
    );
  }
  return (
    <span className={style} title={title}>
      <span className="truncate">{children}</span>
      {onRemove ? (
        <button aria-label={removeLabel ?? "Remove"} className="-mr-1 ml-0.5 grid h-5 w-5 place-items-center rounded-full hover:bg-black/10" onClick={onRemove} type="button">
          <X size={12} aria-hidden="true" />
        </button>
      ) : null}
    </span>
  );
}
