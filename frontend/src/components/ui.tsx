import type { ButtonHTMLAttributes, ReactNode } from "react";
import { DIFFICULTY_CLASSES, TONE_CLASSES, verdictTone } from "../lib/format";
import type { Difficulty } from "../lib/types";

/* ---------------------------------------------------------------- Aurora */

export function AuroraBackdrop() {
  return (
    <>
      <div className="aurora-field" aria-hidden="true">
        <div className="aurora-blob aurora-blob--one" />
        <div className="aurora-blob aurora-blob--two" />
        <div className="aurora-blob aurora-blob--three" />
      </div>
      <div className="aurora-grain" aria-hidden="true" />
    </>
  );
}

/* ----------------------------------------------------------------- Glass */

export function Card({
  children,
  className = "",
  hover = false,
  solid = false,
  edge = false,
  style,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  solid?: boolean;
  edge?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={style}
      className={[
        solid ? "glass-solid" : "glass",
        hover ? "glass-hover" : "",
        edge ? "glass-edge" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}

/* --------------------------------------------------------------- Buttons */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
  loading?: boolean;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  loading = false,
  children,
  className = "",
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={[
        variant === "primary" ? "btn-primary" : "btn-ghost",
        "inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5",
        "text-sm font-semibold text-white",
        className,
      ].join(" ")}
    >
      {loading && <Spinner size={15} />}
      {children}
    </button>
  );
}

export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className="animate-spin"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="2.5"
        opacity="0.22"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ---------------------------------------------------------------- Badges */

export function Badge({
  children,
  tone = "muted",
  className = "",
}: {
  children: ReactNode;
  tone?: keyof typeof TONE_CLASSES;
  className?: string;
}) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
        "text-[11px] font-semibold tracking-wide uppercase",
        TONE_CLASSES[tone],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}

export function VerdictBadge({
  verdict,
  className = "",
}: {
  verdict: string;
  className?: string;
}) {
  const { tone, icon } = verdictTone(verdict);
  return (
    <Badge tone={tone} className={className}>
      {/* The glyph means colour is never the only signal. */}
      <span aria-hidden="true">{icon}</span>
      {verdict}
    </Badge>
  );
}

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
        "text-[11px] font-semibold tracking-wide uppercase",
        DIFFICULTY_CLASSES[difficulty] ?? DIFFICULTY_CLASSES.Easy,
      ].join(" ")}
    >
      <span
        className="size-1.5 rounded-full bg-current"
        aria-hidden="true"
      />
      {difficulty}
    </span>
  );
}

/* ------------------------------------------------------------ Feedback */

export function Alert({
  children,
  tone = "fail",
}: {
  children: ReactNode;
  tone?: keyof typeof TONE_CLASSES;
}) {
  return (
    <div
      role="alert"
      className={[
        "rounded-xl border px-4 py-3 text-sm",
        TONE_CLASSES[tone],
      ].join(" ")}
    >
      {children}
    </div>
  );
}

export function EmptyState({
  icon = "◇",
  title,
  description,
  action,
}: {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <div
        className="grid size-14 place-items-center rounded-2xl border border-white/12 bg-white/5 text-2xl text-violet-200/70"
        aria-hidden="true"
      >
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-violet-50">{title}</h3>
      {description && (
        <p className="max-w-sm text-sm text-violet-200/60">{description}</p>
      )}
      {action}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="animate-rise">
        {eyebrow && (
          <p className="mb-2 text-xs font-semibold tracking-[0.2em] text-violet-300/70 uppercase">
            {eyebrow}
          </p>
        )}
        <h1 className="text-3xl font-bold tracking-tight text-violet-50 sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-sm text-violet-200/60">{description}</p>
        )}
      </div>
      {actions}
    </header>
  );
}

/** Metric readout — numbers in monospace so columns of them align. */
export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "pass" | "fail" | "warn" | "info";
}) {
  const valueColour =
    tone === "pass"
      ? "text-emerald-300"
      : tone === "fail"
        ? "text-rose-300"
        : tone === "warn"
          ? "text-amber-300"
          : tone === "info"
            ? "text-sky-300"
            : "text-violet-50";

  return (
    <Card className="glass-edge p-5" hover>
      <p className="text-[11px] font-semibold tracking-[0.14em] text-violet-300/60 uppercase">
        {label}
      </p>
      <p
        className={`mt-2 font-mono text-2xl font-bold tabular-nums ${valueColour}`}
      >
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-violet-200/45">{hint}</p>}
    </Card>
  );
}

/* ----------------------------------------------------------------- Forms */

import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, TableHTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";

export function Input({ className = "", ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input className={["field", className].join(" ")} {...rest} />
  );
}

export function Textarea({ className = "", ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea className={["field min-h-[100px] resize-y", className].join(" ")} {...rest} />
  );
}

export function Select({ className = "", children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select className={["field appearance-none pr-10", className].join(" ")} {...rest}>
        {children}
      </select>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-violet-300/60">
        <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Layout */

export function PageContainer({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={["mx-auto max-w-7xl px-4 sm:px-6 w-full", className].join(" ")}>
      {children}
    </div>
  );
}

export function Section({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <section className={["py-8 sm:py-12", className].join(" ")}>
      {children}
    </section>
  );
}

/* ---------------------------------------------------------------- Tables */

export function Table({ className = "", children, ...rest }: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto rounded-xl border border-white/10 bg-white/[0.02]">
      <table className={["w-full text-left text-sm text-violet-100", className].join(" ")} {...rest}>
        {children}
      </table>
    </div>
  );
}

export function Thead({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <thead className={["border-b border-white/10 bg-white/5 text-xs font-semibold uppercase tracking-wider text-violet-300/80", className].join(" ")}>
      {children}
    </thead>
  );
}

export function Tbody({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <tbody className={["divide-y divide-white/5", className].join(" ")}>
      {children}
    </tbody>
  );
}

export function Tr({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <tr className={["transition-colors hover:bg-white/[0.04]", className].join(" ")}>
      {children}
    </tr>
  );
}

export function Th({ className = "", children, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={["px-4 py-3 sm:px-6", className].join(" ")} {...rest}>
      {children}
    </th>
  );
}

export function Td({ className = "", children, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={["whitespace-nowrap px-4 py-3 sm:px-6", className].join(" ")} {...rest}>
      {children}
    </td>
  );
}

/* ------------------------------------------------------------- Overlays */

export function Modal({ isOpen, onClose, title, children }: { isOpen: boolean; onClose: () => void; title: string; children: ReactNode }) {
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <Card className="relative w-full max-w-lg shadow-2xl animate-rise" solid>
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <h2 className="text-lg font-semibold text-violet-50">{title}</h2>
          <button onClick={onClose} className="text-violet-300/60 transition-colors hover:text-white" aria-label="Close">
            <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6">
          {children}
        </div>
      </Card>
    </div>
  );
}

export function Tabs({ tabs, activeId, onChange }: { tabs: { id: string; label: string }[]; activeId: string; onChange: (id: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-white/10 px-1">
      {tabs.map((tab) => {
        const isActive = tab.id === activeId;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={[
              "mb-[-1px] border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              isActive ? "border-violet-400 text-violet-200" : "border-transparent text-violet-300/50 hover:border-white/20 hover:text-violet-200/80",
            ].join(" ")}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
