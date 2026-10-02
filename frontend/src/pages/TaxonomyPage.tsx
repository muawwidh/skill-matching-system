import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, FileUp, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";

import {
  importBundledTaxonomySample,
  importTaxonomyRelease,
  listTaxonomyMappings,
  listTaxonomyVersions,
  searchTaxonomy,
} from "../api/taxonomy";
import { useAuth } from "../features/auth/AuthProvider";
import { TaxonomyReviewPanel } from "../components/TaxonomyReviewPanel";

type ImportSource = "esco" | "onet" | "mappings";

export function TaxonomyPage() {
  const { accessToken, user } = useAuth();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [source, setSource] = useState<ImportSource>("esco");
  const [version, setVersion] = useState("");
  const [releaseDate, setReleaseDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const isTaxonomyAdmin = user?.roles.some((role) => role.name === "admin" || role.name === "researcher");

  const versionsQuery = useQuery({
    queryKey: ["taxonomy", "versions"],
    queryFn: () => listTaxonomyVersions(accessToken as string),
    enabled: Boolean(accessToken && isTaxonomyAdmin),
  });
  const mappingsQuery = useQuery({
    queryKey: ["taxonomy", "mappings"],
    queryFn: () => listTaxonomyMappings(accessToken as string),
    enabled: Boolean(accessToken && isTaxonomyAdmin),
  });
  const searchQuery = useQuery({
    queryKey: ["taxonomy", "search", submittedQuery],
    queryFn: () => searchTaxonomy(accessToken as string, submittedQuery),
    enabled: Boolean(accessToken && submittedQuery.length >= 2),
  });

  function refreshTaxonomyData() {
    queryClient.invalidateQueries({ queryKey: ["taxonomy"] });
  }

  const sampleMutation = useMutation({
    mutationFn: () => importBundledTaxonomySample(accessToken as string),
    onSuccess: refreshTaxonomyData,
  });
  const importMutation = useMutation({
    mutationFn: () =>
      importTaxonomyRelease(
        accessToken as string,
        source,
        file as File,
        version,
        releaseDate,
      ),
    onSuccess: () => {
      setFile(null);
      refreshTaxonomyData();
    },
  });

  if (user && !isTaxonomyAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  }

  function submitImport(event: FormEvent) {
    event.preventDefault();
    if (file && version.trim()) {
      importMutation.mutate();
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="text-sm font-medium text-ocean">Administration</p>
        <h1 className="mt-1 text-3xl font-semibold text-ink">Taxonomy management</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Import versioned ESCO and O*NET releases, inspect local concepts, and review uncertain links.
        </p>
      </header>

      <section className="border-t border-slate-200 pt-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">Taxonomy releases</h2>
            <p className="mt-1 text-sm text-slate-600">
              Official imports are the primary data source. The bundled sample is only for local testing.
            </p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            disabled={sampleMutation.isPending}
            onClick={() => sampleMutation.mutate()}
            type="button"
          >
            <Database size={17} aria-hidden="true" />
            Load development sample
          </button>
        </div>

        <form className="mt-5 grid gap-3 border-y border-slate-200 py-5 md:grid-cols-5" onSubmit={submitImport}>
          <label className="text-sm font-medium text-slate-700">
            Dataset
            <select className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2" value={source} onChange={(event) => setSource(event.target.value as ImportSource)}>
              <option value="esco">ESCO release</option>
              <option value="onet">O*NET release</option>
              <option value="mappings">ESCO–O*NET mappings</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Version
            <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" onChange={(event) => setVersion(event.target.value)} placeholder={source === "esco" ? "1.2.1" : source === "onet" ? "29.0 or 31.0" : "Mapping version"} value={version} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Release date
            <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" disabled={source === "mappings"} onChange={(event) => setReleaseDate(event.target.value)} type="date" value={releaseDate} />
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-1">
            Import file
            <input accept={source === "mappings" ? ".json,.csv,.tsv,.txt" : ".zip,.json,.csv,.tsv,.txt"} className="mt-1 block w-full text-sm" onChange={(event) => setFile(event.target.files?.[0] ?? null)} type="file" />
          </label>
          <div className="flex items-end">
            <button className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-ocean px-3 py-2 text-sm font-medium text-white disabled:opacity-50" disabled={!file || !version.trim() || importMutation.isPending} type="submit">
              <FileUp size={17} aria-hidden="true" /> Import
            </button>
          </div>
        </form>
        {source === "onet" ? <p className="text-sm text-slate-600">Official packages: O*NET 29.0 TXT ZIP or O*NET 31.0 CSV ZIP. No 31.0 TXT support.</p> : null}
        {sampleMutation.error || importMutation.error ? <p className="mt-3 text-sm text-red-700">{(sampleMutation.error ?? importMutation.error)?.message}</p> : null}

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase text-slate-500"><tr><th className="py-2 pr-4">Source</th><th className="py-2 pr-4">Version</th><th className="py-2 pr-4">Release</th><th className="py-2 pr-4">Mode</th><th className="py-2">Status</th></tr></thead>
            <tbody>{(versionsQuery.data ?? []).map((item) => <tr className="border-b border-slate-100" key={item.id}><td className="py-3 pr-4 font-medium text-ink">{item.source_code}</td><td className="py-3 pr-4">{item.version}</td><td className="py-3 pr-4">{item.release_date || "Not supplied"}</td><td className="py-3 pr-4"><span className={`rounded px-2 py-1 text-xs ${item.is_sample ? "bg-amber-100 text-ember" : "bg-emerald-100 text-emerald-800"}`}>{item.is_sample ? "Sample" : "Official"}</span></td><td className="py-3">{item.status}</td></tr>)}</tbody>
          </table>
          {!versionsQuery.isLoading && (versionsQuery.data?.length ?? 0) === 0 ? <p className="py-4 text-sm text-slate-500">No taxonomy release has been imported.</p> : null}
        </div>
      </section>

      <section className="border-t border-slate-200 pt-6">
        <h2 className="text-lg font-semibold text-ink">Concept search</h2>
        <form className="mt-3 flex max-w-xl gap-2" onSubmit={submitSearch}>
          <input className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2" onChange={(event) => setQuery(event.target.value)} placeholder="Search skills or occupations" value={query} />
          <button className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-ocean text-white" aria-label="Search taxonomy" type="submit"><Search size={18} aria-hidden="true" /></button>
        </form>
        <div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">
          {(searchQuery.data ?? []).map((concept) => <article className="py-4" key={concept.id}><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-ink">{concept.preferred_label}</h3><span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{concept.source_code} {concept.taxonomy_version}</span><span className="text-xs text-slate-500">{concept.concept_type}</span></div><p className="mt-1 text-sm text-slate-600">{concept.description || "No description supplied."}</p>{concept.alternative_labels.length ? <p className="mt-2 text-xs text-slate-500">Also: {concept.alternative_labels.join(", ")}</p> : null}</article>)}
        </div>
      </section>

      {accessToken && isTaxonomyAdmin ? <TaxonomyReviewPanel accessToken={accessToken} /> : null}

      <section className="border-t border-slate-200 pt-6">
        <h2 className="text-lg font-semibold text-ink">ESCO–O*NET occupation mappings</h2>
        <div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">{(mappingsQuery.data ?? []).map((mapping) => <div className="grid gap-1 py-3 text-sm md:grid-cols-[1fr_auto_1fr] md:items-center" key={mapping.id}><span>{mapping.esco_label}</span><span className="text-slate-400">maps to</span><span className="font-medium text-ink">{mapping.onet_code} · {mapping.onet_title}</span></div>)}</div>
      </section>
    </div>
  );
}
