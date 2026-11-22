type FormFieldProps = {
  label: string;
  error?: string;
  children: React.ReactNode;
};

export function FormField({ label, error, children }: FormFieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-ink">{label}</span>
      {children}
      {error ? <span className="mt-1 block text-sm text-miss-text">{error}</span> : null}
    </label>
  );
}
