import { zodResolver } from "@hookform/resolvers/zod";
import { LogIn } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
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
      title="Skill Gap Matching"
      subtitle="Sign in to review recommendations"
      footerText="New here?"
      footerLinkText="Create an account"
      footerHref="/register"
    >
      <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)}>
        <FormField label="Email" error={form.formState.errors.email?.message}>
          <input className="w-full rounded-md border border-slate-300 px-3 py-2" {...form.register("email")} />
        </FormField>
        <FormField label="Password" error={form.formState.errors.password?.message}>
          <input className="w-full rounded-md border border-slate-300 px-3 py-2" type="password" {...form.register("password")} />
        </FormField>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        <button className="flex w-full items-center justify-center gap-2 rounded-md bg-ocean px-4 py-2.5 font-medium text-white hover:bg-teal-800" type="submit">
          <LogIn size={18} aria-hidden="true" />
          Sign in
        </button>
      </form>
    </AuthCard>
  );
}
