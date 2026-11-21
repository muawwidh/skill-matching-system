import type { Occupation } from "../types/experience";

type OccupationPickerProps = {
  accessToken: string;
  title: string;
  value: Occupation | null;
  onChange: (occupation: Occupation | null) => void;
};

/** Placeholder until occupation suggestions exist (D060 item 3): shows the chosen occupation, if any. */
export function OccupationPicker({ value, onChange }: OccupationPickerProps) {
  return (
    <div className="text-sm text-slate-600">
      ESCO occupation: {value ? value.label : "none"}
      {value ? (
        <button className="ml-2 underline" onClick={() => onChange(null)} type="button">
          Clear
        </button>
      ) : null}
    </div>
  );
}
