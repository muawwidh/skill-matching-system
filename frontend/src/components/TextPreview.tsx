import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

type TextPreviewProps = {
  title: string;
  text: string;
};

export function TextPreview({ title, text }: TextPreviewProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="rounded-lg border border-line bg-white">
      <button
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm font-medium text-ink"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        <span>{title}</span>
        {isOpen ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
      </button>
      {isOpen ? (
        <pre className="max-h-80 overflow-auto border-t border-line bg-mist p-3 whitespace-pre-wrap text-xs leading-5 text-ink">
          {text || "No text available."}
        </pre>
      ) : null}
    </div>
  );
}
