import type { Difficulty } from "./types";

/** Verdict → semantic colour + icon. Colour never carries meaning alone. */
export function verdictTone(verdict: string): {
  tone: "pass" | "fail" | "warn" | "info" | "muted";
  icon: string;
} {
  switch (verdict) {
    case "Accepted":
      return { tone: "pass", icon: "✓" };
    case "Wrong Answer":
      return { tone: "fail", icon: "✕" };
    case "Time Limit Exceeded":
      return { tone: "warn", icon: "◴" };
    case "Memory Limit Exceeded":
    case "Output Limit Exceeded":
      return { tone: "warn", icon: "▲" };
    case "Runtime Error":
      return { tone: "fail", icon: "!" };
    case "Compilation Error":
      return { tone: "info", icon: "⌥" };
    case "Pending":
      return { tone: "muted", icon: "◌" };
    default:
      return { tone: "muted", icon: "?" };
  }
}

export const TONE_CLASSES: Record<string, string> = {
  pass: "text-emerald-300 bg-emerald-400/12 border-emerald-400/30",
  fail: "text-rose-300 bg-rose-400/12 border-rose-400/30",
  warn: "text-amber-300 bg-amber-400/12 border-amber-400/30",
  info: "text-sky-300 bg-sky-400/12 border-sky-400/30",
  muted: "text-violet-200/70 bg-white/6 border-white/12",
};

export const DIFFICULTY_CLASSES: Record<Difficulty, string> = {
  Easy: "text-emerald-300 bg-emerald-400/12 border-emerald-400/25",
  Medium: "text-amber-300 bg-amber-400/12 border-amber-400/25",
  Hard: "text-rose-300 bg-rose-400/12 border-rose-400/25",
};

export const LANGUAGE_LABELS: Record<string, string> = {
  python: "Python 3.11",
  cpp: "C++17",
  java: "Java 21",
};

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function relativeTime(iso: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["second", 60],
    ["minute", 60],
    ["hour", 24],
    ["day", 7],
    ["week", 4.35],
    ["month", 12],
    ["year", Infinity],
  ];

  let value = seconds;
  for (const [unit, size] of units) {
    if (Math.abs(value) < size) {
      return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(
        -Math.round(value),
        unit,
      );
    }
    value /= size;
  }
  return iso;
}

/** Countdown to (or since) a moment, as a compact H:MM:SS style string. */
export function countdown(target: string): string {
  const delta = new Date(target).getTime() - Date.now();
  const abs = Math.abs(delta);

  const days = Math.floor(abs / 86_400_000);
  const hours = Math.floor((abs % 86_400_000) / 3_600_000);
  const minutes = Math.floor((abs % 3_600_000) / 60_000);
  const seconds = Math.floor((abs % 60_000) / 1000);

  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

export function formatMemory(kb: number): string {
  if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`;
  return `${kb} KB`;
}
