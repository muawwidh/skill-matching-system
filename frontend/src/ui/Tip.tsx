import { Info } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/**
 * ⓘ button with a short explanation: shown on hover, keyboard focus or click; Escape closes it.
 * The text is always linked with aria-describedby, so screen readers read it with the button.
 */
export function Tip({ label, children, align = "center", text }: {
  label: string; children: ReactNode; align?: "center" | "left" | "right"; text?: ReactNode;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);
  const position = align === "left" ? "left-0" : align === "right" ? "right-0" : "left-1/2 -translate-x-1/2";
  return (
    <span ref={root} className="relative inline-flex items-center" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        aria-describedby={id}
        aria-expanded={open}
        aria-label={label}
        className="inline-flex items-center gap-1 rounded-full text-muted transition-colors hover:text-ink"
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((value) => !value)}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); }}
        type="button"
      >
        {text ? <span className="text-xs font-medium">{text}</span> : null}
        <Info size={14} aria-hidden="true" />
      </button>
      <span
        className={`absolute top-full z-30 mt-2 w-64 rounded-lg border border-line bg-white p-3 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-ink shadow-[0_10px_30px_-12px_rgba(18,22,28,0.35)] ${position} ${open ? "" : "hidden"}`}
        id={id}
        role="tooltip"
      >
        {children}
      </span>
    </span>
  );
}
