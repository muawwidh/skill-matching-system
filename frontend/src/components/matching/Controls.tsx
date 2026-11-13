import { cloneElement, useId, type ReactElement } from "react";
import { AlertCircle, LoaderCircle } from "lucide-react";

export function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return <div className="match-field"><label htmlFor={id}>{label}</label>{cloneElement(children, { id })}</div>;
}
export function Options({ values, ...props }: { values: readonly string[] } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props}>{values.map(value => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}</select>;
}
export function ErrorNotice({ error }: { error: Error | null }) {
  if (!error) return null;
  return <p role="alert" className="match-error"><AlertCircle size={18} aria-hidden="true" />{error.message}</p>;
}
export function Loading() { return <p role="status" className="flex gap-2"><LoaderCircle size={18} aria-hidden="true" />Loading reviewed inputs...</p>; }
export const reviews = ["pending", "approved", "rejected"] as const;
export const classifications = ["unknown", "required", "preferred", "non_requirement"] as const;
