import type { Num } from "./types";

export const TZ = "Asia/Tashkent";
const LOCALES: Record<string, string> = { uz: "uz-Latn-UZ", ru: "ru-RU", en: "en-GB" };

export function toNum(v: Num | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Group digits with spaces (local convention), no currency symbol. */
export function fmtNum(v: Num | undefined, lang = "uz", maxFrac?: number): string {
  const n = toNum(v);
  if (n === null) return "—";
  const frac = maxFrac ?? (Math.abs(n) >= 100 ? 0 : 2);
  return new Intl.NumberFormat(LOCALES[lang] ?? "uz-Latn-UZ", { maximumFractionDigits: frac }).format(n).replace(/[  ,]/g, " ");
}

export function fmtUZS(v: Num | undefined, lang = "uz"): string {
  const n = toNum(v);
  if (n === null) return "—";
  return `${fmtNum(n, lang)} ${lang === "ru" ? "сум" : lang === "en" ? "UZS" : "so'm"}`;
}

export function fmtDate(v: string | null | undefined, lang = "uz", withTime = false): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(LOCALES[lang] ?? "uz-Latn-UZ", {
    timeZone: TZ, year: "numeric", month: "short", day: "2-digit", ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(d);
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export function ageHours(iso: string | null | undefined): number | null {
  if (!iso) return null;
  return (Date.now() - new Date(iso).getTime()) / 3_600_000;
}
