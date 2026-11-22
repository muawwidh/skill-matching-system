import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { suggestOccupations } from "../api/experience";
import { searchTaxonomy } from "../api/taxonomy";
import type { Occupation } from "../types/experience";
import { occupationSearchResults, preselectedOccupation } from "../utils/occupations";

/** undefined: nothing chosen yet; null: "None of these". */
export type OccupationChoice = Occupation | null | undefined;

type OccupationPickerProps = {
  accessToken: string;
  title: string;
  value: OccupationChoice;
  /** True while the value is the automatic preselection (a strong match), not the candidate's own click. */
  preselected: boolean;
  /** Show the "pick an occupation" hint (the candidate tried to add the entry without a choice). */
  missing: boolean;
  onChange: (occupation: OccupationChoice, preselected: boolean) => void;
};

function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function OccupationLabel({ item }: { item: Occupation }) {
  return (
    <span>
      <span className="font-medium text-ink">{item.label}</span>
      {item.isco_unit_group ? <span className="block text-xs text-slate-500">{item.isco_unit_group}</span> : null}
    </span>
  );
}

/** ESCO occupations of the active release matching the typed text, through the taxonomy search. */
function OccupationSearch({ accessToken, onPick }: { accessToken: string; onPick: (occupation: Occupation) => void }) {
  const [text, setText] = useState("");
  const query = useDebounced(text.trim());
  const results = useQuery({
    queryKey: ["occupation-search", query],
    queryFn: () => searchTaxonomy(accessToken, query, { source: "ESCO", conceptType: "occupation", limit: 50 }),
    enabled: query.length > 1,
    staleTime: 5 * 60 * 1000,
  });
  const items = occupationSearchResults(results.data ?? [], query);
  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-white p-2">
      <input
        aria-label="Search other occupation"
        autoFocus
        className="w-full rounded-md border border-slate-300 px-2 py-1"
        onChange={(event) => setText(event.target.value)}
        placeholder="Type an occupation, e.g. data analyst"
        value={text}
      />
      {results.isFetching ? <p className="mt-1 text-xs text-slate-500">Searching…</p> : null}
      {query.length > 1 && !results.isFetching && items.length === 0 ? (
        <p className="mt-1 text-xs text-slate-500">No ESCO occupation found.</p>
      ) : null}
      <ul className="mt-1">
        {items.map((item) => (
          <li key={item.concept_id}>
            <button className="w-full rounded px-2 py-1 text-left hover:bg-slate-100" onClick={() => onPick(item)} type="button">
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Top-3 ESCO occupation suggestions for the entered job title (D060). The first one is preselected only when
 * it is a strong string match; otherwise nothing is selected until the candidate picks one or "None of these".
 */
export function OccupationPicker({ accessToken, title, value, preselected, missing, onChange }: OccupationPickerProps) {
  const query = useDebounced(title.trim());
  const [searching, setSearching] = useState(false);
  const suggestions = useQuery({
    queryKey: ["occupation-suggestions", query],
    queryFn: () => suggestOccupations(accessToken, query),
    enabled: query.length > 1,
    staleTime: 5 * 60 * 1000,
  });
  const ready = query.length <= 1 || (suggestions.isSuccess && !suggestions.isFetching);
  const data = query.length > 1 ? suggestions.data : undefined;

  // Preselect a strong match while the candidate has not chosen; follow the title while it is only preselected.
  useEffect(() => {
    if (!ready || (value !== undefined && !preselected)) return;
    const strong = preselectedOccupation(data ?? []);
    if (strong && value?.concept_id !== strong.concept_id) onChange(strong, true);
    else if (!strong && value !== undefined) onChange(undefined, false);
  }, [ready, data, value, preselected, onChange]);

  const options: Occupation[] = [...(data ?? [])];
  if (value && !options.some((item) => item.concept_id === value.concept_id)) options.unshift(value);
  const meaningBased = (data ?? []).some((item) => item.method === "embedding");

  return (
    <fieldset className="text-sm">
      <legend className="text-slate-700">ESCO occupation</legend>
      {query.length <= 1 ? <p className="mt-1 text-xs text-slate-500">Type the job title to see suggestions.</p> : null}
      {suggestions.isFetching ? <p className="mt-1 text-xs text-slate-500">Looking up occupations…</p> : null}
      {query.length > 1 && ready && options.length === 0 ? (
        <p className="mt-1 text-xs text-slate-500">No matching ESCO occupation. Search for another one, or choose None of these.</p>
      ) : null}
      <div className="mt-1 space-y-1.5">
        {options.map((item) => (
          <label key={item.concept_id} className="flex items-start gap-2">
            <input className="mt-1" checked={value?.concept_id === item.concept_id} name="occupation" type="radio" onChange={() => onChange(item, false)} />
            <OccupationLabel item={item} />
          </label>
        ))}
        <label className="flex items-center gap-2">
          <input checked={value === null} name="occupation" type="radio" onChange={() => onChange(null, false)} />
          <span>None of these (not used for related experience)</span>
        </label>
      </div>
      {meaningBased ? (
        <p className="mt-1 text-xs text-slate-500">Some suggestions are based on similar meaning rather than matching words. Check that they fit.</p>
      ) : null}
      {searching ? (
        <OccupationSearch accessToken={accessToken} onPick={(occupation) => { onChange(occupation, false); setSearching(false); }} />
      ) : (
        <button className="mt-2 text-sm font-medium text-ocean hover:text-teal-900" onClick={() => setSearching(true)} type="button">
          Search other occupation…
        </button>
      )}
      {missing && value === undefined ? (
        <p role="alert" className="mt-2 text-sm text-amber-800">
          Pick an occupation so this experience can be compared with jobs, or choose None of these
        </p>
      ) : null}
    </fieldset>
  );
}
