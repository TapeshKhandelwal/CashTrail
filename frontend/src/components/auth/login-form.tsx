"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, Eye, EyeOff, HandCoins, Landmark, ShieldCheck, type LucideIcon } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { useLogin } from "@/features/auth/api";
import type { ApiError } from "@/lib/api/errors";
import { DEMO_ACCOUNTS, DEMO_MODE, type DemoAccount } from "@/lib/demo";
import { cn } from "@/lib/utils";

const ROLE_ICON: Record<DemoAccount["role"], LucideIcon> = {
  AGENT: HandCoins,
  BRANCH_MANAGER: Building2,
  FINANCE: Landmark,
  ADMIN: ShieldCheck,
};

const schema = z.object({
  username: z.string().trim().min(1, "Enter your username or email."),
  password: z.string().min(1, "Enter your password."),
});

type LoginValues = z.infer<typeof schema>;

function loginErrorMessage(error: ApiError): string {
  if (error.status === 429 || error.is("THROTTLED")) return "Too many attempts. Try again in a minute.";
  if (error.status === 401 || error.is("NO_ACTIVE_ACCOUNT", "AUTHENTICATION_FAILED")) {
    return "That username and password don't match.";
  }
  return error.friendlyMessage;
}

export function LoginForm() {
  const next = useSearchParams().get("next");
  const login = useLogin();
  const [showPassword, setShowPassword] = useState(false);
  const [demoPending, setDemoPending] = useState<string | null>(null);

  // The router keeps this page's state while it is hidden; coming back after signing out must
  // not find the previous sign-in still "succeeded" and every button disabled.
  const { reset } = login;
  useEffect(
    () => () => {
      reset();
      setDemoPending(null);
    },
    [reset],
  );

  const form = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: "", password: "" },
  });
  const { errors } = form.formState;

  const submit = form.handleSubmit((values) => {
    setDemoPending(null);
    login.mutate({ ...values, next });
  });
  const busy = login.isPending || login.isSuccess;

  const signInAs = (account: DemoAccount) => {
    form.setValue("username", account.username);
    form.setValue("password", account.password);
    form.clearErrors();
    setDemoPending(account.username);
    login.mutate({ username: account.username, password: account.password, next }, { onError: () => setDemoPending(null) });
  };

  return (
    <div className="flex flex-col gap-9">
      <form onSubmit={submit} noValidate className="flex flex-col gap-5">
        <FieldGroup className="gap-4">
          <Field data-invalid={Boolean(errors.username) || undefined}>
            <FieldLabel htmlFor="username" className="text-[13px] text-ink">
              Username or email
            </FieldLabel>
            <Input
              id="username"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              enterKeyHint="next"
              aria-invalid={Boolean(errors.username) || undefined}
              {...form.register("username")}
            />
            <FieldError errors={[errors.username]} />
          </Field>
          <Field data-invalid={Boolean(errors.password) || undefined}>
            <FieldLabel htmlFor="password" className="text-[13px] text-ink">
              Password
            </FieldLabel>
            <InputGroup>
              <InputGroupInput
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                enterKeyHint="go"
                className="text-base md:text-sm"
                aria-invalid={Boolean(errors.password) || undefined}
                {...form.register("password")}
              />
              <InputGroupAddon align="inline-end">
                <InputGroupButton
                  size="icon-sm"
                  className="text-faint hover:text-ink"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff /> : <Eye />}
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
            <FieldError errors={[errors.password]} />
          </Field>
        </FieldGroup>

        {login.isError && (
          <p role="alert" className="flex items-start gap-2.5 rounded-lg bg-st-rejected/8 px-3.5 py-2.5 text-[13px] text-st-rejected-fg animate-rise">
            <span aria-hidden className="mt-[7px] size-1.5 shrink-0 rounded-full bg-st-rejected" />
            {loginErrorMessage(login.error)}
          </p>
        )}

        <Button type="submit" size="lg" className="w-full" loading={busy && !demoPending}>
          Sign in
        </Button>
      </form>

      {DEMO_MODE && (
        <section aria-labelledby="demo-heading" className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <h2 id="demo-heading" className="eyebrow">
              Or open the demo as
            </h2>
            <span aria-hidden className="h-px flex-1 bg-rule" />
          </div>
          <ul className="grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((account) => {
              const pending = demoPending === account.username && busy;
              const Icon = ROLE_ICON[account.role];
              return (
                <li key={account.username} className="h-full">
                  <button
                    type="button"
                    disabled={busy}
                    aria-busy={pending || undefined}
                    onClick={() => signInAs(account)}
                    className={cn(
                      "group/chip flex h-full w-full flex-col gap-3 rounded-xl border border-rule bg-raised p-3.5 text-left transition-[border-color,background-color,box-shadow] duration-200 outline-none hover:border-ink/25 hover:shadow-[0_8px_24px_-16px_rgb(18_20_23/0.35)] focus-visible:ring-3 focus-visible:ring-focus disabled:cursor-default",
                      pending && "border-ink/40 bg-sunk",
                      busy && !pending && "opacity-50",
                    )}
                  >
                    <span className="flex w-full items-center justify-between">
                      <span className="grid size-8 place-items-center rounded-lg border border-rule bg-sunk text-dim transition-colors group-hover/chip:border-brand/30 group-hover/chip:text-brand">
                        <Icon className="size-4" strokeWidth={1.75} />
                      </span>
                      {pending ? (
                        <Spinner className="size-3.5 text-dim" />
                      ) : (
                        <span aria-hidden className="text-faint transition-transform duration-150 group-hover/chip:translate-x-0.5">
                          →
                        </span>
                      )}
                    </span>
                    <span className="flex flex-col gap-0.5">
                      <span className="text-[13.5px] font-medium text-ink">{account.label}</span>
                      <span className="text-[12px] leading-snug text-dim">{account.duty}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="font-mono text-[11px] text-faint">Demo password {DEMO_ACCOUNTS[0].password}</p>
        </section>
      )}
    </div>
  );
}
