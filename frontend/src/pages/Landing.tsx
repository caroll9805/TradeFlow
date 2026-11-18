import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Bot, Building2, Database, Map, Scale, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCategories } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { Overview } from "@/lib/types";
import { fmtNum } from "@/lib/format";
import { LanguageSwitcher, Logo, SimulatedBanner } from "@/components/Layout";
import { Button, Card } from "@/components/ui";

export default function Landing() {
  const { t, nm, lang } = useI18n();
  const { user } = useAuth();
  const { data: ov } = useQuery({ queryKey: ["overview-landing"], queryFn: () => api.get<Overview>("/analytics/overview") });
  const { data: cats } = useCategories();
  const features = [
    { icon: <Scale className="h-5 w-5" />, k: "compare" },
    { icon: <BarChart3 className="h-5 w-5" />, k: "analytics" },
    { icon: <Map className="h-5 w-5" />, k: "regions" },
    { icon: <Bot className="h-5 w-5" />, k: "ai" },
    { icon: <Building2 className="h-5 w-5" />, k: "suppliers" },
    { icon: <ShieldCheck className="h-5 w-5" />, k: "provenance" },
  ];
  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
        <Logo />
        <div className="ml-auto flex items-center gap-3">
          <LanguageSwitcher />
          {user ? <Link to="/dashboard"><Button size="sm">{t("landing.openApp")}</Button></Link> : <>
            <Link to="/login" className="text-sm font-medium text-primary">{t("nav.login")}</Link>
            <Link to="/register"><Button size="sm">{t("nav.register")}</Button></Link>
          </>}
        </div>
      </header>
      <SimulatedBanner />
      <section className="mx-auto max-w-6xl px-4 pb-12 pt-14 md:pt-20">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">{t("landing.kicker")}</p>
        <h1 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight tracking-tight md:text-5xl">{t("landing.title")}</h1>
        <p className="mt-4 max-w-2xl text-base text-muted-foreground md:text-lg">{t("landing.subtitle")}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/catalog"><Button size="lg">{t("landing.ctaCatalog")}</Button></Link>
          <Link to="/assistant"><Button size="lg" variant="outline"><Bot className="h-4 w-4" />{t("landing.ctaAssistant")}</Button></Link>
        </div>
        {ov && (
          <div className="mt-12 grid grid-cols-2 gap-3 md:grid-cols-4">
            {[["products", ov.products_indexed], ["suppliers", ov.suppliers_registered], ["offers", ov.active_offers],
              ["observations", ov.price_observations]].map(([k, v]) => (
              <Card key={k as string} className="p-4">
                <div className="text-2xl font-semibold">{fmtNum(v as number, lang)}</div>
                <div className="text-xs text-muted-foreground">{t(`landing.stat.${k}`)}</div>
              </Card>
            ))}
          </div>
        )}
        {ov && ov.simulated_active_offers > 0 && <p className="mt-2 text-xs text-red-700">{t("landing.simNote")}</p>}
      </section>
      <section className="border-y border-border bg-slate-50 py-12">
        <div className="mx-auto grid max-w-6xl gap-4 px-4 md:grid-cols-3">
          {features.map((f) => (
            <Card key={f.k} className="p-5">
              <div className="mb-3 grid h-9 w-9 place-items-center rounded-md bg-primary/10 text-primary">{f.icon}</div>
              <h3 className="text-sm font-semibold">{t(`landing.f.${f.k}`)}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{t(`landing.f.${f.k}.d`)}</p>
            </Card>
          ))}
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="text-lg font-semibold">{t("landing.categories")}</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {cats?.map((c) => (
            <Link key={c.id} to={`/catalog?category=${c.id}`} className="rounded-full border border-border px-3 py-1.5 text-sm hover:border-primary hover:text-primary">{nm(c)}</Link>
          ))}
        </div>
      </section>
      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        <Database className="mr-1 inline h-3 w-3" />{t("landing.footer")}
      </footer>
    </div>
  );
}
