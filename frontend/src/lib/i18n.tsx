import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import en from "@/locales/en";
import ru from "@/locales/ru";
import uz from "@/locales/uz";

export type Lang = "uz" | "ru" | "en";
export type Dict = Record<string, string>;
const DICTS: Record<Lang, Dict> = { uz, ru, en };
const KEY = "tf_lang";

export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  let s = DICTS[lang][key] ?? DICTS.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

interface Ctx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Localised name from an object with name_uz / name_ru / name_en fields. */
  nm: (o: { name_uz?: string; name_ru?: string; name_en?: string | null } | null | undefined) => string;
  /** Localised option label from label_uz / label_ru. */
  lbl: (o: { label_uz: string; label_ru: string } | null | undefined) => string;
}

const I18nContext = createContext<Ctx | null>(null);

function initialLang(): Lang {
  const s = typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null;
  return s === "ru" || s === "en" || s === "uz" ? s : "uz";
}

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial ?? initialLang());
  const setLang = useCallback((l: Lang) => {
    localStorage.setItem(KEY, l);
    document.documentElement.lang = l;
    setLangState(l);
  }, []);
  const value = useMemo<Ctx>(() => ({
    lang,
    setLang,
    t: (k, v) => translate(lang, k, v),
    nm: (o) => (o ? ((lang === "ru" ? o.name_ru : lang === "en" ? o.name_en : o.name_uz) || o.name_uz || o.name_ru || "") : ""),
    lbl: (o) => (o ? (lang === "ru" ? o.label_ru : o.label_uz) : ""),
  }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const c = useContext(I18nContext);
  if (!c) throw new Error("useI18n must be used inside I18nProvider");
  return c;
}
