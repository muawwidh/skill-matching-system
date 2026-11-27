import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions, id }: { title: string; subtitle?: ReactNode; actions?: ReactNode; id?: string }) {
  return (
    <div className="flex animate-rise flex-wrap items-end justify-between gap-4">
      <div>
        <h1 id={id} className="text-4xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle ? <div className="mt-1.5 text-sm text-muted">{subtitle}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  );
}

export function CardTitle({ id, children, aside }: { id?: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h2 id={id} className="flex items-center gap-2 text-lg font-semibold text-ink">{children}</h2>
      {aside}
    </div>
  );
}

/** Staggered rise on load: index × 60 ms (capped), no motion when reduced motion is requested. */
export function riseDelay(index: number): { animationDelay: string } {
  return { animationDelay: `${Math.min(index, 12) * 60}ms` };
}
