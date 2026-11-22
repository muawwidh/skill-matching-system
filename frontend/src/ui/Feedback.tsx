import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** Grey placeholder block shown while data loads. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-lg bg-neutral-bg ${className}`} />;
}

/** A few skeleton lines with a screen-reader status. */
export function LoadingBlock({ label = "Loading", lines = 3 }: { label?: string; lines?: number }) {
  return (
    <div role="status" className="space-y-2">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} className={`h-4 ${index === lines - 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }: { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-card border border-dashed border-line bg-white px-6 py-10 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-full bg-teal-soft text-teal">
        <Icon size={22} aria-hidden="true" />
      </span>
      <h3 className="mt-3 text-lg font-semibold text-ink">{title}</h3>
      {children ? <div className="mt-1 max-w-md text-sm text-muted">{children}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Notice({ tone = "caution", children }: { tone?: "caution" | "info"; children: ReactNode }) {
  const style = tone === "caution"
    ? "border border-dashed border-caution-line bg-caution-bg text-caution-text"
    : "border border-line bg-teal-soft text-teal-text";
  return <div role="status" className={`rounded-xl px-4 py-3 text-sm ${style}`}>{children}</div>;
}

export function ErrorText({ error }: { error: Error | null | undefined }) {
  return error ? <p role="alert" className="text-sm text-miss-text">{error.message}</p> : null;
}
