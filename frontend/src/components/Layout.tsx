import { useState, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Bell, Bookmark, Bot, Boxes, Building2, ClipboardList, Database, FlaskConical, LayoutDashboard, LogOut,
  Map, Menu, Package, Settings, Shield, Store, TrendingUp, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n, type Lang } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { Overview } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge, LoadingState, Select, Switch } from "@/components/ui";

interface NavItem { to: string; label: string; icon: ReactNode; show?: boolean }

export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex items-center gap-2 font-semibold tracking-tight", className)}>
      <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-white"><TrendingUp className="h-4 w-4" /></span>
      TradeFlow
    </Link>
  );
}

export function LanguageSwitcher() {
  const { lang, setLang, t } = useI18n();
  return (
    <Select value={lang} onChange={(e) => setLang(e.target.value as Lang)} className="h-8 w-auto text-xs" aria-label={t("nav.language")}>
      <option value="uz">O'zbekcha</option>
      <option value="ru">Русский</option>
      <option value="en">English</option>
    </Select>
  );
}

export function SimulatedBanner() {
  const { includeSimulated } = usePrefs();
  const { t } = useI18n();
  const { data } = useQuery({ queryKey: ["overview-sim"], queryFn: () => api.get<Overview>("/analytics/overview"), staleTime: 60_000 });
  if (!includeSimulated || !data?.simulated_active_offers) return null;
  return (
    <div className="flex items-center gap-2 border-b border-red-200 bg-red-50 px-4 py-1.5 text-xs text-red-800" role="note">
      <FlaskConical className="h-3.5 w-3.5 shrink-0" />
      <span>{t("simulated.banner", { n: data.simulated_active_offers })}</span>
    </div>
  );
}

export default function AppLayout() {
  const { user, loading, logout, can } = useAuth();
  const { t } = useI18n();
  const { includeSimulated, setIncludeSimulated } = usePrefs();
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  const { data: notes } = useQuery({ queryKey: ["notifications"], queryFn: () => api.get<{ id: number; read_at: string | null }[]>("/notifications"),
    enabled: !!user, refetchInterval: 60_000 });
  const unread = notes?.filter((n) => !n.read_at).length ?? 0;
  const isSupplier = can("suppliers.manage_own");

  const items: NavItem[] = [
    { to: "/dashboard", label: t("nav.dashboard"), icon: <LayoutDashboard className="h-4 w-4" /> },
    { to: "/catalog", label: t("nav.catalog"), icon: <Package className="h-4 w-4" /> },
    { to: "/suppliers", label: t("nav.suppliers"), icon: <Building2 className="h-4 w-4" /> },
    { to: "/analytics", label: t("nav.analytics"), icon: <BarChart3 className="h-4 w-4" /> },
    { to: "/regions", label: t("nav.regions"), icon: <Map className="h-4 w-4" /> },
    { to: "/assistant", label: t("nav.assistant"), icon: <Bot className="h-4 w-4" /> },
    { to: "/saved", label: t("nav.saved"), icon: <Bookmark className="h-4 w-4" />, show: !!user },
    { to: "/procurement", label: t("nav.procurement"), icon: <ClipboardList className="h-4 w-4" />, show: can("quotes.request") },
    { to: "/supplier", label: t("nav.supplierDashboard"), icon: <Store className="h-4 w-4" />, show: isSupplier },
    { to: "/admin/market-data", label: t("nav.marketData"), icon: <Database className="h-4 w-4" />, show: can("market_data.manage") },
    { to: "/admin/platform", label: t("nav.platformAdmin"), icon: <Shield className="h-4 w-4" />,
      show: can("catalog.manage") || can("users.manage") || can("settings.manage") },
  ];

  if (loading) return <LoadingState />;

  const sidebar = (
    <nav className="flex flex-col gap-0.5 p-3" aria-label={t("nav.main")}>
      {items.filter((i) => i.show !== false).map((i) => (
        <NavLink key={i.to} to={i.to} onClick={() => setOpen(false)}
          className={({ isActive }) => cn("flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
            isActive ? "bg-primary/10 font-medium text-primary" : "text-slate-600 hover:bg-muted hover:text-foreground")}>
          {i.icon}{i.label}
        </NavLink>
      ))}
      <div className="mt-4 border-t border-border px-3 pt-4">
        <Switch id="sim-toggle" checked={includeSimulated} onChange={setIncludeSimulated} label={t("simulated.toggle")} />
        <p className="mt-1 text-[11px] leading-tight text-muted-foreground">{t("simulated.toggleHint")}</p>
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-[500] flex h-14 items-center gap-3 border-b border-border bg-white/95 px-4 backdrop-blur">
        <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label={t("nav.menu")}>{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
        <Logo />
        <Badge tone="slate" className="hidden sm:inline-flex"><Boxes className="h-3 w-3" />{t("app.tagline")}</Badge>
        <div className="ml-auto flex items-center gap-2">
          <LanguageSwitcher />
          {user ? (
            <>
              <Link to="/settings#notifications" className="relative rounded-md p-2 hover:bg-muted" aria-label={t("nav.notifications")}>
                <Bell className="h-4 w-4" />
                {unread > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500" />}
              </Link>
              <Link to="/settings" className="hidden items-center gap-1 rounded-md px-2 py-1 text-sm hover:bg-muted md:flex" aria-label={t("nav.settings")}>
                <Settings className="h-4 w-4" />{user.full_name}
              </Link>
              <button className="rounded-md p-2 hover:bg-muted" aria-label={t("nav.logout")}
                onClick={async () => { await logout(); nav("/"); }}><LogOut className="h-4 w-4" /></button>
            </>
          ) : (
            <>
              <Link to="/login" state={{ from: loc.pathname }} className="text-sm font-medium text-primary">{t("nav.login")}</Link>
              <Link to="/register" className="hidden rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white sm:inline">{t("nav.register")}</Link>
            </>
          )}
        </div>
      </header>
      <SimulatedBanner />
      <div className="flex flex-1">
        <aside className={cn("w-60 shrink-0 border-r border-border bg-white", open ? "fixed inset-y-14 left-0 z-[400] block overflow-y-auto" : "hidden lg:block")}>
          {sidebar}
        </aside>
        <main className="min-w-0 flex-1 bg-slate-50/60 p-4 md:p-6"><Outlet /></main>
      </div>
    </div>
  );
}

export function RequireAuth({ perm, children }: { perm?: string; children: ReactNode }) {
  const { user, loading, can } = useAuth();
  const loc = useLocation();
  const { t } = useI18n();
  if (loading) return <LoadingState />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (perm && !can(perm)) return <div className="py-16 text-center text-sm text-muted-foreground">{t("common.forbidden")}</div>;
  return <>{children}</>;
}
