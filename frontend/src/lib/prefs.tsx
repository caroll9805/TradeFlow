import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

/** Global data preferences. Simulated demo data is visible by default but always labelled,
 *  and can be excluded everywhere with one switch. */
interface Prefs { includeSimulated: boolean; setIncludeSimulated: (v: boolean) => void }
const PrefsContext = createContext<Prefs | null>(null);
const KEY = "tf_include_simulated";

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [includeSimulated, set] = useState<boolean>(() => localStorage.getItem(KEY) !== "false");
  const value = useMemo(() => ({
    includeSimulated,
    setIncludeSimulated: (v: boolean) => { localStorage.setItem(KEY, String(v)); set(v); },
  }), [includeSimulated]);
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): Prefs {
  const c = useContext(PrefsContext);
  if (!c) throw new Error("usePrefs must be used inside PrefsProvider");
  return c;
}
