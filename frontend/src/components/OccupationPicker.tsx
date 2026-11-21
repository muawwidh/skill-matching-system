import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { suggestOccupations } from "../api/experience";
import type { Occupation } from "../types/experience";

type OccupationPickerProps = {
  accessToken: string;
  title: string;
  value: Occupation | null;
  onChange: (occupation: Occupation | null) => void;
};

function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/**
 * Top-5 ESCO occupation suggestions for the entered job title (D060). The candidate picks one or
 * none; only entries with an occupation count towards related experience.
 */
export function OccupationPicker({ accessToken, title, value, onChange }: OccupationPickerProps) {
  const query = useDebounced(title.trim());
  const suggestions = useQuery({
    queryKey: ["occupation-suggestions", query],
    queryFn: () => suggestOccupations(accessToken, query),
    enabled: query.length > 1,
    staleTime: 5 * 60 * 1000,
  });
  const options = [...(suggestions.data ?? [])];
  if (value && !options.some((item) => item.concept_id === value.concept_id)) options.unshift({ ...value, confidence: 0 });

  return (
    <fieldset className="text-sm">
      <legend className="text-slate-700">ESCO occupation</legend>
      {query.length <= 1 ? <p className="mt-1 text-xs text-slate-500">Type the job title to see suggestions.</p> : null}
      {suggestions.isFetching ? <p className="mt-1 text-xs text-slate-500">Looking up occupations…</p> : null}
      {query.length > 1 && !suggestions.isFetching && options.length === 0 ? (
        <p className="mt-1 text-xs text-slate-500">No matching ESCO occupation. Try a more common title, or save without one.</p>
      ) : null}
      <div className="mt-1 space-y-1">
        {options.map((item) => (
          <label key={item.concept_id} className="flex items-start gap-2">
            <input checked={value?.concept_id === item.concept_id} name="occupation" type="radio" onChange={() => onChange(item)} />
            <span>
              {item.label}
              {item.isco_code ? <span className="text-xs text-slate-500"> · ISCO {item.isco_code} {item.isco_unit_group}</span> : null}
            </span>
          </label>
        ))}
        <label className="flex items-center gap-2">
          <input checked={value === null} name="occupation" type="radio" onChange={() => onChange(null)} />
          <span>None of these (not used for related experience)</span>
        </label>
      </div>
    </fieldset>
  );
}
