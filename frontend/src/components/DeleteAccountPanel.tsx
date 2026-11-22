import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { deleteAccount } from "../api/auth";
import { useAuth } from "../features/auth/AuthProvider";

/** "Delete my account and data" for candidate accounts. */
export function DeleteAccountPanel({ accessToken }: { accessToken: string }) {
  const { signOut } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [understood, setUnderstood] = useState(false);

  const mutation = useMutation({
    mutationFn: () => deleteAccount(accessToken, password),
    onSuccess: () => {
      queryClient.clear();
      signOut();
      navigate("/login", { replace: true, state: { accountDeleted: true } });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (password && understood && !mutation.isPending) mutation.mutate();
  }

  return (
    <section className="rounded-lg border border-red-200 bg-white p-5" aria-labelledby="delete-account-heading">
      <h2 id="delete-account-heading" className="text-lg font-semibold text-ink">Delete my account and data</h2>
      <p className="mt-2 text-sm text-slate-600">
        This permanently deletes your account, all of your CVs, the skills found in them and the skills you added, your
        decisions on those skills, your work entries, your Jobs page settings and the profile used to find jobs for you.
        It cannot be undone.
      </p>
      {!open ? (
        <button className="mt-3 inline-flex items-center gap-2 rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700" onClick={() => setOpen(true)} type="button">
          <Trash2 size={16} aria-hidden="true" />
          Delete my account and data
        </button>
      ) : (
        <form className="mt-3 space-y-3" onSubmit={submit}>
          <label className="block text-sm text-slate-700">
            Confirm with your password
            <input
              autoComplete="current-password"
              className="mt-1 block w-full max-w-sm rounded-md border border-slate-300 px-3 py-2"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input checked={understood} onChange={(event) => setUnderstood(event.target.checked)} type="checkbox" />
            I understand that my account and data are deleted permanently.
          </label>
          {mutation.error ? <p role="alert" className="text-sm text-red-700">{mutation.error.message}</p> : null}
          <div className="flex gap-2">
            <button className="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50" disabled={!password || !understood || mutation.isPending} type="submit">
              {mutation.isPending ? "Deleting..." : "Delete permanently"}
            </button>
            <button className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700" onClick={() => { setOpen(false); setPassword(""); setUnderstood(false); }} type="button">
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
