import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { candidateInputs, inputWriter, ownProfile } from "../api/matching";
import { FactForm } from "../components/matching/FactForm";
import { ErrorNotice, Loading } from "../components/matching/Controls";
import { useAuth } from "../features/auth/AuthProvider";

export function MatchingFactsPage() {
  const { accessToken, user } = useAuth();
  const allowed = user?.roles.some(r => r.name === "candidate");
  const client = useQueryClient();
  const profile = useQuery({ queryKey: ["matching-profile", user?.id], queryFn: () => ownProfile(accessToken!), enabled: Boolean(allowed && accessToken), retry: false });
  const key = ["candidate-matching-inputs", user?.id, profile.data?.id];
  const inputs = useQuery({ queryKey: key, queryFn: () => candidateInputs(accessToken!, profile.data!.id), enabled: Boolean(allowed && profile.data && accessToken), retry: false });
  const action = useMutation({ mutationFn: (fn: (writer: ReturnType<typeof inputWriter>) => Promise<unknown>) => fn(inputWriter(accessToken!, "candidates", profile.data!.id, inputs.data!.fingerprint)), retry: false,
    onSuccess: async () => { await client.invalidateQueries({ queryKey: key }); await client.invalidateQueries({ queryKey: ["matching-run", user?.id] }); } });
  if (!user) return <Loading />;
  if (!allowed) return <p role="alert">Candidate role required. Only your own candidate-confirmed facts are available.</p>;
  const error = action.error || inputs.error || profile.error;
  return <div className="matching-page"><h1>Matching facts</h1><ErrorNotice error={error} />
    <button type="button" disabled={action.isPending} onClick={() => { void inputs.refetch(); action.reset(); }}>Reload current inputs</button>
    {(profile.isLoading || inputs.isLoading) && <Loading />}
    {inputs.data && !inputs.error && <FactForm key={inputs.data.fingerprint} candidate facts={inputs.data.facts} sourceIds={inputs.data.sources.map(x => x.id)}
      disabled={action.isPending || inputs.isFetching || Boolean(action.error)} createDisabled={inputs.data.profile.status !== "active"}
      save={async body => { await action.mutateAsync(writer => writer.fact(body)); }}
      remove={id => { if (window.confirm("Delete this fact? Bound matching history may become unreplayable.")) action.mutate(writer => writer.remove("facts", id)); }} />}
    {inputs.data?.profile.status !== undefined && inputs.data.profile.status !== "active" && <p role="alert">Inactive profile: fact creation is unavailable.</p>}
    {action.isPending && <p role="status">Saving reviewed inputs...</p>}
    {action.isSuccess && <p role="status">Reviewed input saved. Matching runs are not refreshed automatically.</p>}
  </div>;
}
