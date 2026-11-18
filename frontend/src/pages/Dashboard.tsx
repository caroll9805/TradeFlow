import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Building2, Database, Package, Tag } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { Movers, Offer, Overview, RegionStat, SourceFreshness } from "@/lib/types";
import { fmtDate, fmtNum, fmtPct, fmtUZS } from "@/lib/format";
import { Badge, Card, CardBody, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, Stat, Table, Td, Th } from "@/components/ui";
import { CategorySelect, RegionSelect } from "@/components/selects";
import { CategoryBarChart } from "@/components/charts";
import { ProvenanceBadge, SimulatedBadge } from "@/components/badges";

export default function Dashboard() {
  const { t, nm, lang } = useI18n();
  const { includeSimulated } = usePrefs();
  const [category, setCategory] = useState<number | "">("");
  const [region, setRegion] = useState<number | "">("");
  const q = { include_simulated: includeSimulated, category_id: category || undefined, region_id: region || undefined };

  const ov = useQuery({ queryKey: ["overview", q], queryFn: () => api.get<Overview>("/analytics/overview", q) });
  const movers = useQuery({ queryKey: ["movers", q], queryFn: () => api.get<Movers>("/analytics/movers", { ...q, limit: 6 }) });
  const regions = useQuery({ queryKey: ["region-stats", q], queryFn: () => api.get<RegionStat[]>("/analytics/regions", { include_simulated: includeSimulated, category_id: category || undefined }) });
  const recent = useQuery({ queryKey: ["recent", q], queryFn: () => api.get<Offer[]>("/analytics/recent-offers", { ...q, limit: 8 }) });
  const fresh = useQuery({ queryKey: ["freshness"], queryFn: () => api.get<SourceFreshness[]>("/analytics/freshness") });

  return (
    <div>
      <PageHeader title={t("dashboard.title")} description={t("dashboard.subtitle")}
        actions={<><div className="w-48"><CategorySelect value={category} onChange={setCategory} /></div>
          <div className="w-48"><RegionSelect value={region} onChange={setRegion} /></div></>} />
      {ov.isLoading ? <LoadingState /> : ov.error ? <ErrorState error={ov.error} onRetry={() => ov.refetch()} /> : ov.data && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label={t("dashboard.products")} value={fmtNum(ov.data.products_indexed, lang)} icon={<Package className="h-4 w-4" />} />
          <Stat label={t("dashboard.suppliers")} value={fmtNum(ov.data.suppliers_registered, lang)} icon={<Building2 className="h-4 w-4" />}
            sub={t("dashboard.verifiedCount", { n: ov.data.suppliers_verified })} />
          <Stat label={t("dashboard.activeOffers")} value={fmtNum(ov.data.active_offers, lang)} icon={<Tag className="h-4 w-4" />}
            sub={ov.data.simulated_active_offers && includeSimulated ? t("dashboard.simulatedCount", { n: ov.data.simulated_active_offers }) : undefined} />
          <Stat label={t("dashboard.observations")} value={fmtNum(ov.data.price_observations, lang)} icon={<Database className="h-4 w-4" />}
            sub={`${t("dashboard.lastUpdate")}: ${fmtDate(ov.data.last_collected_at, lang, true)}`} />
        </div>
      )}

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader title={t("dashboard.offersByCategory")} />
          <CardBody>
            {ov.data && ov.data.offers_by_category.some((c) => c.offers) ? (
              <CategoryBarChart rows={ov.data.offers_by_category.map((c) => ({ name: nm(c), value: c.offers }))} />
            ) : <EmptyState />}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title={t("dashboard.movers")} description={movers.data?.method} action={<Link to="/analytics" className="text-xs text-primary">{t("common.more")}</Link>} />
          <CardBody className="grid gap-4 md:grid-cols-2">
            {movers.isLoading ? <LoadingState /> : movers.error ? <ErrorState error={movers.error} /> : (
              (["increases", "decreases"] as const).map((k) => (
                <div key={k}>
                  <p className="mb-2 flex items-center gap-1 text-xs font-medium text-muted-foreground">
                    {k === "increases" ? <ArrowUpRight className="h-3.5 w-3.5 text-red-600" /> : <ArrowDownRight className="h-3.5 w-3.5 text-emerald-600" />}
                    {t(`dashboard.${k}`)}
                  </p>
                  {movers.data?.[k].length ? (
                    <ul className="space-y-1.5">
                      {movers.data[k].map((m) => (
                        <li key={m.product_id} className="flex items-center justify-between gap-2 text-sm">
                          <Link to={`/products/${m.product_id}`} className="truncate hover:text-primary">{m.name}</Link>
                          <span className={k === "increases" ? "text-red-600" : "text-emerald-600"}>{fmtPct(m.change_pct)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-xs text-muted-foreground">{t("common.insufficientData")}</p>}
                </div>
              ))
            )}
          </CardBody>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title={t("dashboard.recentOffers")} />
          {recent.isLoading ? <LoadingState /> : recent.error ? <ErrorState error={recent.error} /> : recent.data?.length ? (
            <Table>
              <thead><tr><Th>{t("common.product")}</Th><Th>{t("common.supplier")}</Th><Th>{t("common.region")}</Th>
                <Th className="text-right">{t("common.pricePerUnit")}</Th><Th>{t("common.source")}</Th><Th>{t("common.updated")}</Th></tr></thead>
              <tbody>
                {recent.data.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <Td><Link to={`/products/${o.product.id}`} className="font-medium hover:text-primary">{o.product.name}</Link></Td>
                    <Td><Link to={`/suppliers/${o.supplier.id}`} className="hover:text-primary">{o.supplier.name}</Link></Td>
                    <Td>{nm(o.region)}</Td>
                    <Td className="whitespace-nowrap text-right">{fmtUZS(o.price_per_base_unit_uzs, lang)}<span className="text-xs text-muted-foreground">/{o.product.base_unit}</span></Td>
                    <Td><div className="flex flex-wrap gap-1"><ProvenanceBadge kind={o.provenance_kind} />{o.is_simulated && <SimulatedBadge />}</div></Td>
                    <Td className="whitespace-nowrap text-xs text-muted-foreground">{fmtDate(o.price_updated_at, lang, true)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : <EmptyState />}
        </Card>
        <Card>
          <CardHeader title={t("dashboard.topRegions")} action={<Link to="/regions" className="text-xs text-primary">{t("common.map")}</Link>} />
          <CardBody>
            {regions.data ? (
              <ul className="space-y-2 text-sm">
                {[...regions.data].sort((a, b) => b.active_offers - a.active_offers).slice(0, 8).map((r) => (
                  <li key={r.region_id} className="flex items-center justify-between">
                    <span>{nm(r)}</span>
                    <span className="text-xs text-muted-foreground">{t("dashboard.offersSuppliers", { o: r.active_offers, s: r.suppliers_with_offers })}</span>
                  </li>
                ))}
              </ul>
            ) : <LoadingState />}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-5">
        <CardHeader title={t("dashboard.sources")} description={t("dashboard.sourcesHint")} />
        {fresh.data ? (
          <Table>
            <thead><tr><Th>{t("common.source")}</Th><Th>{t("common.provenance")}</Th><Th>{t("dashboard.reliability")}</Th>
              <Th>{t("dashboard.lastUpdate")}</Th><Th>{t("dashboard.observations")}</Th><Th>{t("common.status")}</Th></tr></thead>
            <tbody>
              {fresh.data.map((s) => (
                <tr key={s.source_id}>
                  <Td className="font-medium">{s.name} {s.is_simulated && <SimulatedBadge />}</Td>
                  <Td><ProvenanceBadge kind={s.provenance} /></Td>
                  <Td>{fmtNum(s.reliability_score, lang, 2)}</Td>
                  <Td className="text-xs">{fmtDate(s.last_collected_at, lang, true)}</Td>
                  <Td>{fmtNum(s.observations, lang)}</Td>
                  <Td><Badge tone={s.status === "fresh" ? "green" : s.status === "stale" ? "amber" : "slate"}>{t(`freshness.status.${s.status}`)}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : <LoadingState />}
      </Card>
    </div>
  );
}
