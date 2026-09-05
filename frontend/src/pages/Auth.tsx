import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Alert, Button, Card, Input } from "../components/ui";

type Mode = "login" | "register";

export function AuthPage({ mode }: { mode: Mode }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const isRegister = mode === "register";

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    setBusy(true);

    try {
      if (isRegister) {
        await register(username.trim(), email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
      navigate(location.state?.from ?? "/problems", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors?.length) {
        setFieldErrors(
          Object.fromEntries(err.fieldErrors.map((e) => [e.field, e.message])),
        );
        setError("Please correct the highlighted fields.");
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    } finally {
      setBusy(false);
    }
  }

  function fillDemo() {
    setEmail("demo@example.com");
    setPassword("DemoPass123");
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-md items-center px-4 py-12 sm:px-6">
      <Card solid edge className="animate-rise w-full p-8">
        <div className="mb-7 text-center">
          <span
            className="mx-auto mb-4 grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 text-lg font-black text-white shadow-lg shadow-purple-500/30"
            aria-hidden="true"
          >
            J
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-violet-50">
            {isRegister ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-1.5 text-sm text-violet-200/55">
            {isRegister
              ? "Start solving problems in seconds."
              : "Sign in to submit and track your progress."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {error && <Alert tone="fail">{error}</Alert>}

          {isRegister && (
            <Field
              label="Username"
              value={username}
              onChange={setUsername}
              placeholder="ada_lovelace"
              autoComplete="username"
              error={fieldErrors.username}
              hint="Letters, digits, underscore, dot and hyphen."
            />
          )}

          <Field
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@example.com"
            autoComplete="email"
            error={fieldErrors.email}
          />

          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="••••••••"
            autoComplete={isRegister ? "new-password" : "current-password"}
            error={fieldErrors.password}
            hint={
              isRegister
                ? "At least 8 characters, mixing letters with digits or symbols."
                : undefined
            }
          />

          <Button type="submit" loading={busy} className="w-full">
            {isRegister ? "Create account" : "Sign in"}
          </Button>
        </form>

        {!isRegister && (
          <button
            onClick={fillDemo}
            type="button"
            className="mt-3 w-full rounded-xl border border-dashed border-white/15 px-4 py-2.5 text-xs text-violet-200/60 transition-colors hover:border-violet-400/40 hover:text-violet-100"
          >
            Use the demo account
          </button>
        )}

        <p className="mt-6 text-center text-sm text-violet-200/55">
          {isRegister ? "Already have an account?" : "No account yet?"}{" "}
          <Link
            to={isRegister ? "/login" : "/register"}
            className="font-semibold text-violet-300 hover:text-violet-200"
          >
            {isRegister ? "Sign in" : "Create one"}
          </Link>
        </p>
      </Card>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  autoComplete,
  error,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  autoComplete?: string;
  error?: string;
  hint?: string;
}) {
  const id = `field-${label.toLowerCase()}`;
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-xs font-semibold tracking-wide text-violet-200/70 uppercase"
      >
        {label}
      </label>
      <Input
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        style={error ? { borderColor: "rgb(251 113 133 / 0.6)" } : undefined}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-rose-300">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-violet-200/40">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
