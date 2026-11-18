/** Thin fetch client: JSON, bearer auth, one transparent token refresh on 401. */
const BASE = "/api";
const ACCESS = "tf_access";
const REFRESH = "tf_refresh";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : formatDetail(detail) || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

function formatDetail(d: unknown): string {
  if (Array.isArray(d)) {
    return d
      .map((e) => (typeof e === "string" ? e : (e as { msg?: string; loc?: unknown[] }).msg
        ? `${((e as { loc?: unknown[] }).loc ?? []).slice(1).join(".")}: ${(e as { msg: string }).msg}` : JSON.stringify(e)))
      .join("; ");
  }
  return d ? JSON.stringify(d) : "";
}

export const tokens = {
  get access() { return localStorage.getItem(ACCESS); },
  get refresh() { return localStorage.getItem(REFRESH); },
  set(a: string, r: string) { localStorage.setItem(ACCESS, a); localStorage.setItem(REFRESH, r); },
  clear() { localStorage.removeItem(ACCESS); localStorage.removeItem(REFRESH); },
};

type Query = Record<string, string | number | boolean | null | undefined>;

export function qs(params?: Query): string {
  if (!params) return "";
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  });
  const s = u.toString();
  return s ? `?${s}` : "";
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const r = tokens.refresh;
  if (!r) return false;
  refreshing ??= fetch(`${BASE}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: r }),
  })
    .then(async (res) => {
      if (!res.ok) { tokens.clear(); return false; }
      const j = await res.json();
      tokens.set(j.access_token, j.refresh_token);
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function request<T>(method: string, path: string, opts: { query?: Query; body?: unknown; form?: FormData } = {},
  retry = true): Promise<T> {
  const headers: Record<string, string> = {};
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  const res = await fetch(`${BASE}${path}${qs(opts.query)}`, { method, headers, body });
  if (res.status === 401 && retry && tokens.refresh && !path.startsWith("/auth/")) {
    if (await tryRefresh()) return request<T>(method, path, opts, false);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) throw new ApiError(res.status, (data as { detail?: unknown })?.detail ?? data ?? res.statusText);
  return data as T;
}

function safeJson(t: string): unknown {
  try { return JSON.parse(t); } catch { return t; }
}

export const api = {
  get: <T>(p: string, query?: Query) => request<T>("GET", p, { query }),
  post: <T>(p: string, body?: unknown, query?: Query) => request<T>("POST", p, { body, query }),
  put: <T>(p: string, body?: unknown) => request<T>("PUT", p, { body }),
  patch: <T>(p: string, body?: unknown) => request<T>("PATCH", p, { body }),
  del: <T>(p: string) => request<T>("DELETE", p),
  upload: <T>(p: string, form: FormData) => request<T>("POST", p, { form }),
};
