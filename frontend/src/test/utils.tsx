import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import { PrefsProvider } from "@/lib/prefs";

export type Handler = { method?: string; match: RegExp; status?: number; body: unknown | ((url: string, init?: RequestInit) => unknown) };

/** Install a fetch mock that answers by method + URL regex and records every call. */
export function mockFetch(handlers: Handler[]) {
  const calls: { url: string; method: string; body?: unknown }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    calls.push({ url, method, body: init?.body });
    const h = handlers.find((x) => (x.method ?? "GET") === method && x.match.test(url));
    if (!h) return new Response(JSON.stringify({ detail: `unmocked ${method} ${url}` }), { status: 404 });
    const body = typeof h.body === "function" ? (h.body as (u: string, i?: RequestInit) => unknown)(url, init) : h.body;
    return new Response(h.status === 204 ? null : JSON.stringify(body), { status: h.status ?? 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export function renderApp(ui: ReactElement, { route = "/", path = "*" }: { route?: string; path?: string } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initial="en">
        <PrefsProvider>
          <MemoryRouter initialEntries={[route]}>
            <AuthProvider>
              <Routes>
                <Route path={path} element={ui} />
                <Route path="/dashboard" element={<div>DASHBOARD PAGE</div>} />
              </Routes>
            </AuthProvider>
          </MemoryRouter>
        </PrefsProvider>
      </I18nProvider>
    </QueryClientProvider>,
  );
}

export const USER = {
  id: 1, email: "buyer@x.uz", full_name: "Ali", phone: null, locale: "en", is_active: true, role: "buyer",
  role_name: { uz: "Xaridor", ru: "Покупатель" }, permissions: ["quotes.request"], created_at: "2026-01-01T00:00:00Z",
  last_login_at: null, organizations: [{ id: 1, name: "Ali Savdo", org_type: "buyer", member_role: "owner" }],
};
