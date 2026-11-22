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
    <section className="rounded-xl border border-miss-text/25 p-4" aria-labelledby="delete-account-heading">
      <h3 id="delete-account-heading" className="font-semibold text-ink">Delete my account and data</h3>
      <p className="mt-1 text-sm text-muted">
        This permanently deletes your account, all of your CVs, the skills found in them and the skills you added, your
        decisions on those skills, your work entries, your Jobs page settings and the profile used to find jobs for you.
        It cannot be undone.
      </p>
      {!open ? (
        <button className="btn-danger mt-3" onClick={() => setOpen(true)} type="button">
          <Trash2 size={16} aria-hidden="true" />
          Delete my account and data
        </button>
      ) : (
        <form className="mt-3 space-y-3" onSubmit={submit}>
          <label className="block text-sm text-ink">
            Confirm with your password
            <input
              autoComplete="current-password"
              className="field mt-1 block w-full max-w-sm"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input checked={understood} onChange={(event) => setUnderstood(event.target.checked)} type="checkbox" />
            I understand that my account and data are deleted permanently.
          </label>
          {mutation.error ? <p role="alert" className="text-sm text-miss-text">{mutation.error.message}</p> : null}
          <div className="flex gap-2">
            <button className="btn bg-miss-text text-white hover:opacity-90" disabled={!password || !understood || mutation.isPending} type="submit">
              {mutation.isPending ? "Deleting..." : "Delete permanently"}
            </button>
            <button className="btn-secondary" onClick={() => { setOpen(false); setPassword(""); setUnderstood(false); }} type="button">
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
