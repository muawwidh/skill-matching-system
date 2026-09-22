import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { register } from "../api/auth";
import { AuthCard } from "../components/AuthCard";
import { FormField } from "../components/FormField";
import { useAuth } from "../features/auth/AuthProvider";

const schema = z.object({
  full_name: z.string().min(1),
  email: z.string().email(),
  password: z.string().min(8),
});

type FormValues = z.infer<typeof schema>;

export function RegisterPage() {
  const [error, setError] = useState<string | null>(null);
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const form = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      setSession(await register(values));
      navigate("/dashboard");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Registration failed.");
    }
  }

  return (
    <AuthCard
      title="Create Account"
      subtitle="Start a decision-support profile"
      footerText="Already registered?"
      footerLinkText="Sign in"
      footerHref="/login"
    >
      <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)}>
        <FormField label="Full name" error={form.formState.errors.full_name?.message}>
          <input className="w-full rounded-md border border-slate-300 px-3 py-2" {...form.register("full_name")} />
        </FormField>
        <FormField label="Email" error={form.formState.errors.email?.message}>
          <input className="w-full rounded-md border border-slate-300 px-3 py-2" {...form.register("email")} />
        </FormField>
        <FormField label="Password" error={form.formState.errors.password?.message}>
          <input className="w-full rounded-md border border-slate-300 px-3 py-2" type="password" {...form.register("password")} />
        </FormField>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        <button className="flex w-full items-center justify-center gap-2 rounded-md bg-ocean px-4 py-2.5 font-medium text-white hover:bg-teal-800" type="submit">
          <UserPlus size={18} aria-hidden="true" />
          Register
        </button>
      </form>
    </AuthCard>
  );
}
