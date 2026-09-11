import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TableHTMLAttributes,
  TdHTMLAttributes,
  TextareaHTMLAttributes,
  ThHTMLAttributes,
} from "react";
import { TONE_CLASSES, verdictTone } from "../lib/format";
import type { Difficulty } from "../lib/types";

/* ---------------------------------------------------------------- Backdrop */

export function AuroraBackdrop() {
  return <div className="graphite-grid-bg" aria-hidden="true" />;
}

/* ----------------------------------------------------------------- Card */

export function Card({
  children,
  className = "",
  hover = false,
  solid: _solid = false,
  edge: _edge = false,
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
        "graphite-card",
        hover ? "graphite-card-hover" : "",
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
  variant?: "primary" | "ghost" | "accent";
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
  const variantClass =
    variant === "accent"
      ? "btn-lime"
      : variant === "primary"
      ? "btn-secondary"
      : "btn-ghost";

  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={[
        variantClass,
        "inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold transition-all rounded-md",
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
        opacity="0.2"
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

const GRAPHITE_TONE_CLASSES: Record<string, string> = {
  pass: "bg-[#1B2A12] text-[#B7F34A] border border-[#2A3A19]",
  fail: "bg-[#351A1A] text-[#FF6B6B] border border-[#522323]",
  warn: "bg-[#332B15] text-[#F5C451] border border-[#4F4220]",
  info: "bg-[#172638] text-[#70B7FF] border border-[#243B54]",
  muted: "bg-[#1A211F] text-[#A7B2AC] border border-[#2A332F]",
};

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
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5",
        "font-mono text-[11px] font-semibold tracking-wide uppercase",
        GRAPHITE_TONE_CLASSES[tone] ?? GRAPHITE_TONE_CLASSES.muted,
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
      <span aria-hidden="true">{icon}</span>
      {verdict}
    </Badge>
  );
}

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  const toneMap: Record<Difficulty, string> = {
    Easy: "bg-[#1B2A12] text-[#B7F34A] border border-[#2A3A19]",
    Medium: "bg-[#332B15] text-[#F5C451] border border-[#4F4220]",
    Hard: "bg-[#351A1A] text-[#FF6B6B] border border-[#522323]",
  };

  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5",
        "font-mono text-[11px] font-semibold tracking-wide uppercase",
        toneMap[difficulty] ?? toneMap.Easy,
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
  const toneClass =
    tone === "pass"
      ? "bg-[#1B2A12] border-[#2A3A19] text-[#B7F34A]"
      : tone === "warn"
      ? "bg-[#332B15] border-[#4F4220] text-[#F5C451]"
      : tone === "info"
      ? "bg-[#172638] border-[#243B54] text-[#70B7FF]"
      : "bg-[#351A1A] border-[#522323] text-[#FF6B6B]";

  return (
    <div
      role="alert"
      className={[
        "rounded-md border p-3.5 text-xs font-mono font-medium",
        toneClass,
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
        className="grid size-10 place-items-center rounded border border-[#2A332F] bg-[#1A211F] font-mono text-base text-[#A7B2AC]"
        aria-hidden="true"
      >
        {icon}
      </div>
      <h3 className="text-sm font-bold font-mono text-[#F1F5F2] uppercase">{title}</h3>
      {description && (
        <p className="max-w-sm text-xs font-sans text-[#A7B2AC]">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
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
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-[#2A332F] pb-5">
      <div className="animate-swiss-in">
        {eyebrow && (
          <p className="mb-1 font-mono text-[11px] font-semibold tracking-wider text-[#B7F34A] uppercase">
            {eyebrow}
          </p>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-[#F1F5F2] font-mono sm:text-3xl">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-xs font-sans text-[#A7B2AC]">{description}</p>
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
      ? "text-[#B7F34A]"
      : tone === "fail"
      ? "text-[#FF6B6B]"
      : tone === "warn"
      ? "text-[#F5C451]"
      : tone === "info"
      ? "text-[#70B7FF]"
      : "text-[#F1F5F2]";

  return (
    <Card className="p-5" hover>
      <p className="font-mono text-[11px] font-semibold tracking-wider text-[#A7B2AC] uppercase">
        {label}
      </p>
      <p
        className={`mt-1.5 font-mono text-2xl font-bold tabular-nums ${valueColour}`}
      >
        {value}
      </p>
      {hint && <p className="mt-1 text-xs font-mono text-[#6F7B75]">{hint}</p>}
    </Card>
  );
}

/* ----------------------------------------------------------------- Forms */

export function Input({
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={["graphite-input", className].join(" ")} {...rest} />;
}

export function Textarea({
  className = "",
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={["graphite-input min-h-[90px] resize-y", className].join(" ")}
      {...rest}
    />
  );
}

export function Select({
  className = "",
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        className={["graphite-input appearance-none pr-9 font-mono text-xs font-medium", className].join(" ")}
        {...rest}
      >
        {children}
      </select>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-[#6F7B75]">
        <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Layout */

export function PageContainer({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={["mx-auto max-w-7xl px-4 sm:px-6 w-full", className].join(" ")}>
      {children}
    </div>
  );
}

export function Section({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={["py-6 sm:py-8", className].join(" ")}>
      {children}
    </section>
  );
}

/* ---------------------------------------------------------------- Tables */

export function Table({
  className = "",
  children,
  ...rest
}: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto rounded-md border border-[#2A332F] bg-[#141A18]">
      <table
        className={["w-full text-left text-xs font-mono text-[#F1F5F2]", className].join(" ")}
        {...rest}
      >
        {children}
      </table>
    </div>
  );
}

export function Thead({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <thead
      className={[
        "border-b border-[#2A332F] bg-[#1A211F] font-mono text-[11px] font-semibold uppercase tracking-wider text-[#A7B2AC]",
        className,
      ].join(" ")}
    >
      {children}
    </thead>
  );
}

export function Tbody({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <tbody className={["divide-y divide-[#2A332F]", className].join(" ")}>
      {children}
    </tbody>
  );
}

export function Tr({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <tr className={["transition-colors hover:bg-[#1A211F]/80", className].join(" ")}>
      {children}
    </tr>
  );
}

export function Th({
  className = "",
  children,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={["px-4 py-3 sm:px-5", className].join(" ")} {...rest}>
      {children}
    </th>
  );
}

export function Td({
  className = "",
  children,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={["whitespace-nowrap px-4 py-3 sm:px-5", className].join(" ")}
      {...rest}
    >
      {children}
    </td>
  );
}

/* ------------------------------------------------------------- Overlays */

export function Modal({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-swiss-in">
      <div
        className="absolute inset-0 bg-[#0D1110]/80 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative w-full max-w-lg rounded-lg border border-[#39453F] bg-[#141A18] p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#2A332F] pb-3 mb-4">
          <h2 className="text-sm font-bold font-mono text-[#F1F5F2] uppercase">{title}</h2>
          <button
            onClick={onClose}
            className="text-[#6F7B75] hover:text-[#F1F5F2] transition-colors p-1"
            aria-label="Close"
          >
            <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
}

export function Tabs({
  tabs,
  activeId,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  activeId: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-[#2A332F] bg-[#1A211F] p-1 font-mono text-xs">
      {tabs.map((tab) => {
        const isActive = tab.id === activeId;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={[
              "rounded px-3.5 py-1.5 font-semibold transition-all uppercase",
              isActive
                ? "bg-[#141A18] text-[#B7F34A] border border-[#2A332F]"
                : "text-[#A7B2AC] hover:text-[#F1F5F2] hover:bg-[#141A18]",
            ].join(" ")}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

