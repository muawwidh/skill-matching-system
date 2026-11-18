import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { candidateInputs, inputWriter, ownProfile } from "../../api/matching";
import { FactForm } from "./FactForm";
import { ErrorNotice, Loading } from "./Controls";
import { useAuth } from "../../features/auth/AuthProvider";

export function CandidateFactsPanel() {
  const { accessToken, user } = useAuth();
  const allowed = user?.roles.some(r => r.name === "candidate");
  const client = useQueryClient();
  const dirty = useRef(false);
  const editFingerprint = useRef<string>();
  const busy = useRef(false);
  const [epoch, setEpoch] = useState(0);
  const profile = useQuery({ queryKey: ["matching-profile", user?.id], queryFn: () => ownProfile(accessToken!), enabled: Boolean(allowed && accessToken), retry: false });
  const key = ["candidate-matching-inputs", user?.id, profile.data?.id];
  const inputs = useQuery({ queryKey: key, queryFn: () => candidateInputs(accessToken!, profile.data!.id), enabled: Boolean(allowed && profile.data && accessToken), retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false });
  const action = useMutation({ mutationFn: (fn: (writer: ReturnType<typeof inputWriter>) => Promise<unknown>) => fn(inputWriter(accessToken!, "candidates", profile.data!.id, editFingerprint.current || inputs.data!.fingerprint)), retry: false,
    onSuccess: async () => { dirty.current = false; editFingerprint.current = undefined; await client.invalidateQueries({ queryKey: key }); await client.invalidateQueries({ queryKey: ["matching-run", user?.id] }); } });
  async function write(fn: (writer: ReturnType<typeof inputWriter>) => Promise<unknown>) {
    if (busy.current) throw new Error("A request is already pending.");
    busy.current = true;
    try { await action.mutateAsync(fn); } finally { busy.current = false; }
  }
  async function reload() {
    if (busy.current || inputs.isFetching) return;
    if (dirty.current && !window.confirm("Discard unsaved fact fields and reload current inputs?")) return;
    const result = await inputs.refetch();
    if (!result.isError) { dirty.current = false; editFingerprint.current = undefined; setEpoch(x => x + 1); action.reset(); }
  }
  if (!user) return <Loading />;
  if (!allowed) return <p role="alert">Candidate role required. Only your own candidate-confirmed facts are available.</p>;
  const error = action.error || inputs.error || profile.error;
  return <div className="matching-page"><p>Profile-wide candidate-confirmed facts, not facts for only the displayed CV. These claims are not independently verified.</p><ErrorNotice error={error} />
    <button type="button" aria-disabled={action.isPending || inputs.isFetching} onClick={() => { void reload(); }}>Reload current inputs</button>
    {(profile.isLoading || inputs.isLoading) && <Loading />}
    {inputs.data && !inputs.error && <div onChangeCapture={() => { if (!dirty.current) editFingerprint.current = inputs.data.fingerprint; dirty.current = true; }}><FactForm key={`${profile.data?.id}:${epoch}`} candidate facts={inputs.data.facts} sourceIds={inputs.data.sources.map(x => x.id)}
      disabled={action.isPending || inputs.isFetching || Boolean(action.error)} createDisabled={inputs.data.profile.status !== "active"}
      save={body => write(writer => writer.fact(body))}
      remove={id => {
        if (dirty.current) { window.alert("Save or explicitly reload unsaved fact fields before deleting a fact."); return; }
        if (window.confirm("Delete this fact? Bound matching history may become unreplayable.")) void write(writer => writer.remove("facts", id)).catch(() => undefined);
      }} /></div>}
    {inputs.data?.profile.status !== undefined && inputs.data.profile.status !== "active" && <p role="alert">Inactive profile: fact creation is unavailable.</p>}
    {action.isPending && <p role="status">Saving reviewed inputs...</p>}
    {action.isSuccess && <p role="status">Reviewed input saved. Matching runs are not refreshed automatically.</p>}
  </div>;
}
