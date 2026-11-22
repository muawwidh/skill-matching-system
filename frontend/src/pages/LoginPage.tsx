import { zodResolver } from "@hookform/resolvers/zod";
import { LogIn } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { login } from "../api/auth";
import { AuthCard } from "../components/AuthCard";
import { FormField } from "../components/FormField";
import { useAuth } from "../features/auth/AuthProvider";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const accountDeleted = Boolean((useLocation().state as { accountDeleted?: boolean } | null)?.accountDeleted);
  const form = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      setSession(await login(values));
      navigate("/dashboard");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Login failed.");
    }
  }

  return (
    <AuthCard
      title="Sign in"
      subtitle="See the jobs that fit your skills and the skills you are missing."
      footerText="New here?"
      footerLinkText="Create an account"
      footerHref="/register"
    >
      {accountDeleted ? (
        <p role="status" className="mb-4 rounded-lg border border-teal bg-teal-soft p-3 text-sm text-teal-text">
          Your account and data have been deleted.
        </p>
      ) : null}
      <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)}>
        <FormField label="Email" error={form.formState.errors.email?.message}>
          <input className="field w-full" {...form.register("email")} />
        </FormField>
        <FormField label="Password" error={form.formState.errors.password?.message}>
          <input className="field w-full" type="password" {...form.register("password")} />
        </FormField>
        {error ? <p className="text-sm text-miss-text">{error}</p> : null}
        <button className="btn-primary w-full py-2.5" type="submit">
          <LogIn size={18} aria-hidden="true" />
          Sign in
        </button>
      </form>
    </AuthCard>
  );
}
