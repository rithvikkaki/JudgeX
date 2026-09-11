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
      <Card className="animate-swiss-in w-full p-8 bg-[#141A18] border border-[#2A332F] shadow-2xl rounded-md">
        <div className="mb-8 text-center">
          <div
            className="mx-auto mb-4 flex size-12 items-center justify-center bg-[#B7F34A] font-mono text-lg font-bold text-[#0D1110] tracking-widest border border-[#B7F34A] rounded-md"
            aria-hidden="true"
          >
            J
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#F1F5F2] uppercase font-mono">
            {isRegister ? "Create Account" : "System Login"}
          </h1>
          <p className="mt-1.5 text-xs text-[#A7B2AC] font-sans">
            {isRegister
              ? "Register credentials for JudgeX execution engine."
              : "Authenticate to access workbench and submissions."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
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

          <Button type="submit" loading={busy} className="w-full btn-lime py-2.5 font-mono text-xs font-bold uppercase tracking-wider">
            {isRegister ? "Register Account" : "Sign In"}
          </Button>
        </form>

        {!isRegister && (
          <button
            onClick={fillDemo}
            type="button"
            className="mt-4 w-full border border-dashed border-[#2A332F] bg-[#1A211F] px-4 py-2 text-xs font-mono text-[#A7B2AC] transition-colors hover:border-[#39453F] hover:bg-[#202824] hover:text-[#F1F5F2] rounded-md"
          >
            Load Demo Credentials
          </button>
        )}

        <p className="mt-6 text-center text-xs text-[#A7B2AC] font-sans">
          {isRegister ? "Already registered?" : "New user?"}{" "}
          <Link
            to={isRegister ? "/login" : "/register"}
            className="font-semibold text-[#B7F34A] hover:underline underline-offset-2 font-mono"
          >
            {isRegister ? "Sign in" : "Create an account"}
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
        className="mb-1.5 block text-[11px] font-mono font-semibold tracking-wider text-[#A7B2AC] uppercase"
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
        className={error ? "border-[#FF6B6B] focus:border-[#FF6B6B]" : ""}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs font-mono text-[#FF6B6B]">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 text-xs font-mono text-[#6F7B75]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
