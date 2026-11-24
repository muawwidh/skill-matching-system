import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, FileText, FileUp, Lock, Plus, Send, Trash2, UploadCloud } from "lucide-react";
import { DragEvent, FormEvent, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { addManualSkill, deleteCv, getMatchingProfile, listCvs, pasteCv, removeManualSkill, uploadCv } from "../api/documents";
import { listWorkEntries } from "../api/experience";
import { CandidateTaxonomyLinks } from "../components/CandidateTaxonomyLinks";
import { DeleteAccountPanel } from "../components/DeleteAccountPanel";
import { LanguagesPanel } from "../components/LanguagesPanel";
import { SectionList } from "../components/SectionList";
import { SkillReviewPanel } from "../components/SkillReviewPanel";
import { TextPreview } from "../components/TextPreview";
import { WorkEntriesPanel } from "../components/WorkEntriesPanel";
import { useAuth } from "../features/auth/AuthProvider";
import { useSkillSummary } from "../hooks/useSkillSummary";
import type { CvDocument } from "../types/documents";
import type { WorkEntry } from "../types/experience";
import { Chip } from "../ui/Chip";
import { EmptyState, ErrorText, LoadingBlock, Notice, Skeleton } from "../ui/Feedback";
import { CardTitle, PageHeader } from "../ui/Page";
import type { ProfileSkill, SkillSummary } from "../utils/skills";

// --- Matching profile summary ------------------------------------------------------------------------

function MatchingSummary({ accessToken, summary, entries }: { accessToken: string; summary: SkillSummary | null; entries: WorkEntry[] | undefined }) {
  const profile = useQuery({ queryKey: ["matching-profile"], queryFn: () => getMatchingProfile(accessToken) });
  const data = profile.data;
  const stat = (value: number | string | undefined, label: string) => (
    <div>
      <p className="font-display text-3xl font-semibold">{value ?? "–"}</p>
      <p className="text-sm text-night-muted">{label}</p>
    </div>
  );
  return (
    <section className="card-dark" aria-labelledby="matching-profile-heading">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div>
          <h2 id="matching-profile-heading" className="text-lg font-semibold">Your matching profile</h2>
          <p className="mt-1 text-sm text-night-muted">
            Jobs are matched against the skills you confirmed in these CVs and the skills you added yourself.
          </p>
          {profile.isLoading ? <Skeleton className="mt-3 h-10 bg-white/10" /> : null}
          {data ? (
            <ul className="mt-3 flex flex-wrap gap-2 text-sm">
              {data.cvs.map((cv) => (
                <li key={cv.id} className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1">
                  <FileText size={14} aria-hidden="true" /> {cv.original_filename}
                </li>
              ))}
              <li className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1">
                <Plus size={14} aria-hidden="true" /> {data.manual_skills.approved ?? 0} added by you
              </li>
            </ul>
          ) : null}
          {data && data.retrieval_status !== "ready" ? (
            <p role="status" className="mt-3 rounded-lg bg-caution-bg px-3 py-2 text-sm text-caution-text">{data.retrieval_message}</p>
          ) : data ? (
            <p className="mt-3 text-sm text-night-muted">Your matching profile is up to date.</p>
          ) : null}
        </div>
        <div className="grid grid-cols-3 gap-4 self-center">
          {stat(summary?.confirmed, "skills")}
          {stat(summary?.linked, "linked to ESCO")}
          {stat(entries?.length, "work entries")}
        </div>
      </div>
    </section>
  );
}

// --- Skills ------------------------------------------------------------------------------------------

function ChipGroup({ title, skills, kind, hint, onRemove }: {
  title: string; skills: ProfileSkill[]; kind: "matched" | "review" | "neutral"; hint?: string; onRemove?: (skill: ProfileSkill) => void;
}) {
  if (!skills.length) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-ink">
        {title} <span className="font-normal text-muted">({skills.length})</span>
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {skills.map((skill) => (
          <Chip key={skill.key} kind={kind} title={hint ?? (skill.linked ? "Linked to an ESCO skill" : "Not linked to ESCO; matched by name")}
            onRemove={onRemove && skill.manualIds.length ? () => onRemove(skill) : undefined} removeLabel={`Remove ${skill.label}`}>
            {skill.label}
          </Chip>
        ))}
      </div>
    </div>
  );
}

const SKILL_QUERIES = [["manual-skills"], ["cv"], ["matching-profile"], ["recommendations"], ["languages"]];

function AddSkill({ accessToken }: { accessToken: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const add = useMutation({
    mutationFn: () => addManualSkill(accessToken, text),
    onSuccess: () => {
      setText("");
      setOpen(false);
      for (const key of SKILL_QUERIES) queryClient.invalidateQueries({ queryKey: key });
    },
  });
  if (!open) {
    return (
      <button className="btn-secondary" onClick={() => setOpen(true)} type="button">
        <Plus size={16} aria-hidden="true" /> Add a skill
      </button>
    );
  }
  return (
    <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); if (text.trim()) add.mutate(); }}>
      <label className="text-sm text-ink">
        Skill
        <input autoFocus className="field mt-1 block w-56" maxLength={255} onChange={(event) => setText(event.target.value)} placeholder="e.g. Kubernetes" value={text} />
      </label>
      <button className="btn-primary" disabled={!text.trim() || add.isPending} type="submit">Add</button>
      <button className="btn-secondary" onClick={() => setOpen(false)} type="button">Cancel</button>
      <div className="w-full"><ErrorText error={add.error} /></div>
    </form>
  );
}

function SkillsCard({ accessToken, cvs, summary, loading }: {
  accessToken: string; cvs: CvDocument[]; summary: SkillSummary | null; loading: boolean;
}) {
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: (skill: ProfileSkill) => Promise.all(skill.manualIds.map((id) => removeManualSkill(accessToken, id))),
    onSuccess: () => { for (const key of SKILL_QUERIES) queryClient.invalidateQueries({ queryKey: key }); },
  });
  const [reviewOpen, setReviewOpen] = useState(false);
  const reviewRef = useRef<HTMLDivElement>(null);
  const skills = summary?.skills ?? [];
  const confirmed = skills.filter((skill) => skill.kind === "confirmed");
  const review = skills.filter((skill) => skill.kind === "review");
  const added = skills.filter((skill) => skill.kind === "added");

  function openReview() {
    setReviewOpen(true);
    window.setTimeout(() => reviewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  return (
    <section className="card scroll-mt-4" id="skills" aria-labelledby="skills-heading">
      <CardTitle id="skills-heading" aside={<AddSkill accessToken={accessToken} />}>
        Skills
      </CardTitle>
      {review.length ? (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed border-caution-line bg-caution-bg px-4 py-3 text-sm text-caution-text">
          <span className="flex items-center gap-2">
            <AlertTriangle size={16} aria-hidden="true" />
            {review.length} skill{review.length === 1 ? " needs" : "s need"} your review
          </span>
          <button className="btn-secondary px-3 py-1.5" onClick={openReview} type="button">Review now</button>
        </div>
      ) : null}
      {loading ? <LoadingBlock label="Loading skills" lines={4} /> : null}
      {!loading && !skills.length ? (
        <p className="text-sm text-muted">{cvs.length ? "No skills found yet." : "Add a CV to find your skills, or add skills yourself."}</p>
      ) : null}
      <div className="space-y-5">
        <ChipGroup title="Confirmed" skills={confirmed} kind="matched" />
        <ChipGroup title="Needs review" skills={review} kind="review" hint="Found in your CV; confirm or reject it below" />
        <ChipGroup title="Added by you" skills={added} kind="neutral" hint="Added by hand" onRemove={(skill) => remove.mutate(skill)} />
        <ErrorText error={remove.error} />
      </div>
      {cvs.length ? (
        <div ref={reviewRef} className="mt-6 scroll-mt-4 border-t border-line pt-4">
          <button
            aria-expanded={reviewOpen}
            className="flex w-full items-center justify-between text-left text-sm font-semibold text-ink"
            onClick={() => setReviewOpen((value) => !value)}
            type="button"
          >
            Review skills and ESCO links
            <ChevronDown size={18} className={`transition-transform ${reviewOpen ? "rotate-180" : ""}`} aria-hidden="true" />
          </button>
          {reviewOpen ? (
            <div className="mt-3 space-y-6">
              {cvs.map((cv) => (
                <div key={cv.id}>
                  <p className="text-sm font-medium text-muted">From {cv.original_filename}</p>
                  <SkillReviewPanel accessToken={accessToken} ownerId={cv.id} ownerType="cv" />
                  <CandidateTaxonomyLinks accessToken={accessToken} cvId={cv.id} />
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

// --- CVs ---------------------------------------------------------------------------------------------

function AddCv({ accessToken, onDone }: { accessToken: string; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"upload" | "paste">("upload");
  const [consent, setConsent] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: () => uploadCv(accessToken, file as File, consent),
    onSuccess: () => { setFile(null); setConsent(false); onDone(); },
  });
  const paste = useMutation({
    mutationFn: () => pasteCv(accessToken, text, consent),
    onSuccess: () => { setText(""); setConsent(false); onDone(); },
  });
  const pending = upload.isPending || paste.isPending;

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!consent || pending) return;
    if (mode === "upload" && file) upload.mutate();
    if (mode === "paste" && text.trim()) paste.mutate();
  }

  return (
    <form className="space-y-3" onSubmit={submit}>
      {mode === "upload" ? (
        <div
          className={`flex flex-col items-center rounded-xl border-2 border-dashed px-4 py-6 text-center ${dragging ? "border-teal bg-teal-soft" : "border-line bg-mist"}`}
          onDragLeave={() => setDragging(false)}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDrop={drop}
        >
          <UploadCloud size={28} className="text-teal" aria-hidden="true" />
          <p className="mt-2 text-sm text-ink">{file ? file.name : "Drop your CV here"}</p>
          <p className="text-xs text-muted">PDF, Word (DOCX) or plain text, up to 5 MB</p>
          <button className="btn-secondary mt-3 px-3 py-1.5" onClick={() => input.current?.click()} type="button">
            <FileUp size={16} aria-hidden="true" /> Choose a file
          </button>
          <input
            ref={input}
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            aria-label="CV file"
            className="sr-only"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            type="file"
          />
        </div>
      ) : (
        <label className="block text-sm text-ink">
          CV text
          <textarea className="field mt-1 min-h-40 w-full" onChange={(event) => setText(event.target.value)} placeholder="Paste readable CV text here" value={text} />
        </label>
      )}
      <button className="text-sm link" onClick={() => setMode(mode === "upload" ? "paste" : "upload")} type="button">
        {mode === "upload" ? "Paste text instead" : "Upload a file instead"}
      </button>
      <label className="flex items-start gap-2 text-sm text-ink">
        <input checked={consent} className="mt-0.5 accent-teal" onChange={(event) => setConsent(event.target.checked)} type="checkbox" />
        I consent to CV processing for job matching research.
      </label>
      <ErrorText error={upload.error ?? paste.error} />
      <button className="btn-primary w-full" disabled={!consent || pending || (mode === "upload" ? !file : !text.trim())} type="submit">
        {mode === "upload" ? <FileUp size={16} aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}
        {pending ? "Processing…" : mode === "upload" ? "Upload and process" : "Process pasted CV"}
      </button>
    </form>
  );
}

function CvRow({ cv, accessToken, isCandidate, skillCount, entryCount, onDeleted }: {
  cv: CvDocument; accessToken: string; isCandidate: boolean; skillCount: number; entryCount: number; onDeleted: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const [removeEntries, setRemoveEntries] = useState(true);
  const [details, setDetails] = useState(false);
  const remove = useMutation({
    mutationFn: () => deleteCv(accessToken, cv.id, removeEntries),
    onSuccess: () => { setConfirm(false); onDeleted(); },
  });
  return (
    <li className="py-3">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-teal-soft text-teal"><FileText size={18} aria-hidden="true" /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-ink">{cv.original_filename}</p>
          <p className="text-xs text-muted">
            {cv.status} · {skillCount} skill{skillCount === 1 ? "" : "s"}
            {isCandidate ? ` · ${entryCount} work entr${entryCount === 1 ? "y" : "ies"}` : ""}
          </p>
          <button aria-expanded={details} className="mt-1 text-xs link" onClick={() => setDetails((value) => !value)} type="button">
            {details ? "Hide details" : "Show sections and text"}
          </button>
        </div>
        <button aria-label={`Delete ${cv.original_filename}`} className="btn-danger h-9 w-9 p-0" disabled={remove.isPending}
          onClick={() => { setRemoveEntries(true); setConfirm(true); }} type="button">
          <Trash2 size={16} aria-hidden="true" />
        </button>
      </div>
      {confirm ? (
        <div role="alertdialog" aria-labelledby={`delete-${cv.id}-title`} className="mt-3 rounded-xl border border-miss-text/30 bg-miss-bg p-3 text-sm text-miss-text">
          <p id={`delete-${cv.id}-title`} className="font-semibold">Delete {cv.original_filename}?</p>
          <p className="mt-1">
            This permanently removes the CV text and its sections, the skills extracted from this CV together with
            your reviews of them, and their taxonomy links. Skills you added by hand stay in your profile. Job matching
            is then rebuilt from your remaining CVs and manual skills.
          </p>
          {isCandidate && entryCount > 0 ? (
            <label className="mt-2 flex items-center gap-2">
              <input checked={removeEntries} onChange={(event) => setRemoveEntries(event.target.checked)} type="checkbox" />
              Also remove {entryCount} work {entryCount === 1 ? "entry" : "entries"} taken from this CV
            </label>
          ) : null}
          {isCandidate ? <p className="mt-1 text-xs">Work entries you typed in yourself always stay.</p> : null}
          <div className="mt-2"><ErrorText error={remove.error} /></div>
          <div className="mt-3 flex gap-2">
            <button className="btn bg-miss-text text-white hover:opacity-90" disabled={remove.isPending} onClick={() => remove.mutate()} type="button">
              {remove.isPending ? "Deleting..." : "Delete CV"}
            </button>
            <button className="btn-secondary" onClick={() => setConfirm(false)} type="button">Cancel</button>
          </div>
        </div>
      ) : null}
      {details ? (
        <div className="mt-3 space-y-3">
          <SectionList sections={cv.sections} />
          <TextPreview title="Raw extracted text" text={cv.raw_text} />
          <TextPreview title="Cleaned text used for detection" text={cv.cleaned_text} />
        </div>
      ) : null}
    </li>
  );
}

// --- Page --------------------------------------------------------------------------------------------

export function CvsPage() {
  const { accessToken, user } = useAuth();
  const roles = user?.roles.map((role) => role.name) ?? [];
  // Work entries, skills summary and account deletion are candidate-only, like job matching.
  const isCandidate = roles.includes("candidate") && !roles.includes("admin") && !roles.includes("researcher");
  const queryClient = useQueryClient();
  const token = accessToken as string;
  const skillData = useSkillSummary(token, Boolean(accessToken) && isCandidate);
  const cvQuery = useQuery({ queryKey: ["cvs"], queryFn: () => listCvs(token), enabled: Boolean(accessToken) });
  const entries = useQuery({ queryKey: ["work-entries"], queryFn: () => listWorkEntries(token), enabled: Boolean(accessToken) && isCandidate });

  function refresh() {
    for (const key of [["cvs"], ["cv"], ["matching-profile"], ["recommendations"], ["work-entries"], ["manual-skills"], ["languages"]]) {
      queryClient.invalidateQueries({ queryKey: key });
    }
  }

  if (!accessToken) return null;
  const cvs = cvQuery.data ?? [];
  const cvNames = Object.fromEntries(cvs.map((cv) => [cv.id, cv.original_filename]));
  const skillsFrom = (cvId: string) => (skillData.summary?.skills ?? []).filter((skill) => skill.kind !== "review" && skill.cvIds.includes(cvId)).length;
  const entriesFrom = (cvId: string) => (entries.data ?? []).filter((entry) => entry.source_cv_id === cvId).length;

  return (
    <div className="space-y-6">
      <PageHeader title="My profile" subtitle={<span className="inline-flex items-center gap-1.5"><Lock size={14} aria-hidden="true" /> Only you can see it.</span>} />
      {isCandidate ? <MatchingSummary accessToken={token} summary={skillData.summary} entries={entries.data} /> : null}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          {isCandidate ? (
            <SkillsCard accessToken={token} cvs={cvs} summary={skillData.summary} loading={skillData.loading} />
          ) : (
            <section className="card" aria-labelledby="skills-heading">
              <CardTitle id="skills-heading">Skills</CardTitle>
              {cvs.length ? cvs.map((cv) => (
                <div key={cv.id}>
                  <p className="text-sm font-medium text-muted">From {cv.original_filename}</p>
                  <SkillReviewPanel accessToken={token} ownerId={cv.id} ownerType="cv" />
                  <CandidateTaxonomyLinks accessToken={token} cvId={cv.id} />
                </div>
              )) : <p className="text-sm text-muted">Add a CV to find skills.</p>}
            </section>
          )}
          {isCandidate ? <LanguagesPanel accessToken={token} /> : null}
          {isCandidate ? <WorkEntriesPanel accessToken={token} cvNames={cvNames} /> : null}
        </div>
        <div className="space-y-6">
          <section className="card" aria-labelledby="cvs-heading">
            <CardTitle id="cvs-heading">My CVs</CardTitle>
            <AddCv accessToken={token} onDone={refresh} />
            {cvQuery.isLoading ? <div className="mt-4"><LoadingBlock label="Loading CVs" /></div> : null}
            <ErrorText error={cvQuery.error} />
            {cvs.length ? (
              <ul className="mt-4 divide-y divide-line border-t border-line">
                {cvs.map((cv) => (
                  <CvRow key={cv.id} accessToken={token} cv={cv} entryCount={entriesFrom(cv.id)} isCandidate={isCandidate}
                    onDeleted={refresh} skillCount={skillsFrom(cv.id)} />
                ))}
              </ul>
            ) : null}
            {cvQuery.data && !cvs.length ? (
              <div className="mt-4">
                <EmptyState icon={FileText} title="No CV yet">Add your CV to find your skills and see matching jobs.</EmptyState>
              </div>
            ) : null}
          </section>
          {isCandidate ? (
            <section className="card space-y-4" aria-labelledby="your-data-heading">
              <h2 id="your-data-heading" className="text-lg font-semibold text-ink">Your data</h2>
              <p className="text-sm text-muted">
                Your CVs, skills and work entries are visible only to you. Read how your data is handled in the{" "}
                <Link className="link" to="/privacy">privacy notice</Link>.
              </p>
              <DeleteAccountPanel accessToken={token} />
            </section>
          ) : null}
          {isCandidate && skillData.error ? <Notice>{skillData.error.message}</Notice> : null}
        </div>
      </div>
    </div>
  );
}
