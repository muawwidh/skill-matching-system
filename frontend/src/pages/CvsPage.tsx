import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Send, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";

import { deleteCv, listCvs, pasteCv, uploadCv } from "../api/documents";
import { CandidateTaxonomyLinks } from "../components/CandidateTaxonomyLinks";
import { MatchingProfileBox } from "../components/MatchingProfileBox";
import { SectionList } from "../components/SectionList";
import { SkillReviewPanel } from "../components/SkillReviewPanel";
import { TextPreview } from "../components/TextPreview";
import { useAuth } from "../features/auth/AuthProvider";

export function CvsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [cvText, setCvText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [pasteConsent, setPasteConsent] = useState(false);
  const [uploadConsent, setUploadConsent] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  function invalidateProfile() {
    queryClient.invalidateQueries({ queryKey: ["cvs"] });
    queryClient.invalidateQueries({ queryKey: ["matching-profile"] });
    queryClient.invalidateQueries({ queryKey: ["recommendations"] });
  }

  const deleteMutation = useMutation({
    mutationFn: (cvId: string) => deleteCv(accessToken as string, cvId),
    onSuccess: () => {
      setConfirmDelete(null);
      invalidateProfile();
    },
  });

  const cvQuery = useQuery({
    queryKey: ["cvs"],
    queryFn: () => listCvs(accessToken as string),
    enabled: Boolean(accessToken),
  });

  const pasteMutation = useMutation({
    mutationFn: () => pasteCv(accessToken as string, cvText, pasteConsent),
    onSuccess: () => {
      setCvText("");
      setPasteConsent(false);
      invalidateProfile();
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => uploadCv(accessToken as string, file as File, uploadConsent),
    onSuccess: () => {
      setFile(null);
      setUploadConsent(false);
      invalidateProfile();
    },
  });

  function submitPastedCv(event: FormEvent) {
    event.preventDefault();
    if (pasteConsent && !pasteMutation.isPending) pasteMutation.mutate();
  }

  function submitUploadedCv(event: FormEvent) {
    event.preventDefault();
    if (file && uploadConsent && !uploadMutation.isPending) {
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
            <input checked={pasteConsent} onChange={(event) => setPasteConsent(event.target.checked)} type="checkbox" />
            I consent to CV processing for job matching research.
          </label>
          {pasteMutation.error ? <p className="mt-3 text-sm text-red-700">{pasteMutation.error.message}</p> : null}
          <button className="mt-4 flex items-center gap-2 rounded-md bg-ocean px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50" disabled={!pasteConsent || pasteMutation.isPending} type="submit">
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
          <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
            <input checked={uploadConsent} onChange={(event) => setUploadConsent(event.target.checked)} type="checkbox" />
            I consent to CV processing for job matching research.
          </label>
          {uploadMutation.error ? <p className="mt-3 text-sm text-red-700">{uploadMutation.error.message}</p> : null}
          <button className="mt-4 flex items-center gap-2 rounded-md border border-slate-300 px-4 py-2 font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50" disabled={!file || !uploadConsent || uploadMutation.isPending} type="submit">
            <FileUp size={18} aria-hidden="true" />
            Upload and process
          </button>
        </form>
      </section>

      <div className="space-y-6">
      {accessToken ? <MatchingProfileBox accessToken={accessToken} /> : null}
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
                <div className="flex items-center gap-3">
                  <span className="text-sm text-slate-500">{cv.sections.length} sections</span>
                  <button
                    className="inline-flex items-center gap-1 rounded-md border border-red-300 px-2 py-1 text-sm text-red-700 disabled:opacity-50"
                    disabled={deleteMutation.isPending}
                    onClick={() => setConfirmDelete(cv.id)}
                    type="button"
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    Delete CV
                  </button>
                </div>
              </div>
              {confirmDelete === cv.id ? (
                <div role="alertdialog" aria-labelledby={`delete-${cv.id}-title`} className="mt-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                  <p id={`delete-${cv.id}-title`} className="font-semibold">Delete {cv.original_filename}?</p>
                  <p className="mt-1">
                    This permanently removes the CV text and its sections, the skills extracted from this CV together with
                    your reviews of them, and their taxonomy links. Skills you added by hand stay in your profile. Job matching
                    is then rebuilt from your remaining CVs and manual skills.
                  </p>
                  {deleteMutation.error ? <p role="alert" className="mt-2 text-red-700">{deleteMutation.error.message}</p> : null}
                  <div className="mt-3 flex gap-2">
                    <button className="rounded-md bg-red-700 px-3 py-1.5 font-medium text-white disabled:opacity-50" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(cv.id)} type="button">
                      {deleteMutation.isPending ? "Deleting..." : "Delete CV"}
                    </button>
                    <button className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-slate-700" onClick={() => setConfirmDelete(null)} type="button">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : null}
              <div className="mt-4">
                <SectionList sections={cv.sections} />
              </div>
              <div className="mt-4 space-y-3">
                <TextPreview title="Raw extracted text" text={cv.raw_text} />
                <TextPreview title="Cleaned text used for detection" text={cv.cleaned_text} />
              </div>
              {accessToken ? (
                <>
                  <SkillReviewPanel accessToken={accessToken} ownerId={cv.id} ownerType="cv" />
                  <CandidateTaxonomyLinks accessToken={accessToken} cvId={cv.id} />
                </>
              ) : null}
            </article>
          ))}
          {cvQuery.data?.length === 0 ? <p className="text-sm text-slate-500">No CVs processed yet.</p> : null}
        </div>
      </section>
      </div>
    </div>
  );
}
