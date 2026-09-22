import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Send } from "lucide-react";
import { FormEvent, useState } from "react";

import { listCvs, pasteCv, uploadCv } from "../api/documents";
import { SectionList } from "../components/SectionList";
import { SkillReviewPanel } from "../components/SkillReviewPanel";
import { TextPreview } from "../components/TextPreview";
import { useAuth } from "../features/auth/AuthProvider";

export function CvsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [cvText, setCvText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(true);

  const cvQuery = useQuery({
    queryKey: ["cvs"],
    queryFn: () => listCvs(accessToken as string),
    enabled: Boolean(accessToken),
  });

  const pasteMutation = useMutation({
    mutationFn: () => pasteCv(accessToken as string, cvText, consent),
    onSuccess: () => {
      setCvText("");
      queryClient.invalidateQueries({ queryKey: ["cvs"] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => uploadCv(accessToken as string, file as File, consent),
    onSuccess: () => {
      setFile(null);
      queryClient.invalidateQueries({ queryKey: ["cvs"] });
    },
  });

  function submitPastedCv(event: FormEvent) {
    event.preventDefault();
    pasteMutation.mutate();
  }

  function submitUploadedCv(event: FormEvent) {
    event.preventDefault();
    if (file) {
      uploadMutation.mutate();
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <section className="space-y-6">
        <form className="rounded-lg border border-slate-200 bg-white p-5" onSubmit={submitPastedCv}>
          <h1 className="text-xl font-semibold text-ink">Paste CV Text</h1>
          <textarea
            className="mt-4 min-h-56 w-full rounded-md border border-slate-300 px-3 py-2"
            onChange={(event) => setCvText(event.target.value)}
            placeholder="Paste readable CV text here"
            value={cvText}
          />
          <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
            <input checked={consent} onChange={(event) => setConsent(event.target.checked)} type="checkbox" />
            I consent to CV processing for job matching research.
          </label>
          {pasteMutation.error ? <p className="mt-3 text-sm text-red-700">{pasteMutation.error.message}</p> : null}
          <button className="mt-4 flex items-center gap-2 rounded-md bg-ocean px-4 py-2 font-medium text-white" type="submit">
            <Send size={18} aria-hidden="true" />
            Process pasted CV
          </button>
        </form>

        <form className="rounded-lg border border-slate-200 bg-white p-5" onSubmit={submitUploadedCv}>
          <h2 className="text-xl font-semibold text-ink">Upload CV</h2>
          <input
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            className="mt-4 w-full rounded-md border border-slate-300 px-3 py-2"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            type="file"
          />
          {uploadMutation.error ? <p className="mt-3 text-sm text-red-700">{uploadMutation.error.message}</p> : null}
          <button className="mt-4 flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 font-medium text-slate-700" type="submit">
            <FileUp size={18} aria-hidden="true" />
            Upload and process
          </button>
        </form>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-xl font-semibold text-ink">Processed CVs</h2>
        <div className="mt-4 space-y-4">
          {cvQuery.data?.map((cv) => (
            <article key={cv.id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-ink">{cv.original_filename}</h3>
                  <p className="text-sm text-slate-600">{cv.status} · {cv.content_type}</p>
                </div>
                <span className="text-sm text-slate-500">{cv.sections.length} sections</span>
              </div>
              <div className="mt-4">
                <SectionList sections={cv.sections} />
              </div>
              <div className="mt-4 space-y-3">
                <TextPreview title="Raw extracted text" text={cv.raw_text} />
                <TextPreview title="Cleaned text used for detection" text={cv.cleaned_text} />
              </div>
              {accessToken ? (
                <SkillReviewPanel accessToken={accessToken} ownerId={cv.id} ownerType="cv" />
              ) : null}
            </article>
          ))}
          {cvQuery.data?.length === 0 ? <p className="text-sm text-slate-500">No CVs processed yet.</p> : null}
        </div>
      </section>
    </div>
  );
}
