import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { Offer, Product, RegionalPrice, RegionStat } from "@/lib/types";
import { fmtNum, fmtUZS } from "@/lib/format";
import { Alert, Card, CardBody, CardHeader, EmptyState, ErrorState, Field, LoadingState, PageHeader, Table, Tabs, Td, Th } from "@/components/ui";
import { CategorySelect } from "@/components/selects";
import { UzMap } from "@/components/UzMap";
import { ProductPicker } from "@/components/ProductPicker";
import { RegionalBarChart } from "@/components/charts";
import { ProvenanceBadge, SimulatedBadge } from "@/components/badges";

export default function RegionalAnalytics() {
  const { t, nm, lang } = useI18n();
  const { includeSimulated } = usePrefs();
  const [category, setCategory] = useState<number | "">("");
  const [mode, setMode] = useState<"offers" | "suppliers" | "price">("offers");
  const [selected, setSelected] = useState<number | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const stats = useQuery({ queryKey: ["region-stats", category, includeSimulated],
    queryFn: () => api.get<RegionStat[]>("/analytics/regions", { category_id: category || undefined, include_simulated: includeSimulated }) });
  const prices = useQuery({ queryKey: ["regional", product?.id, includeSimulated], enabled: !!product,
    queryFn: () => api.get<RegionalPrice[]>(`/products/${product!.id}/regional`, { include_simulated: includeSimulated }) });
  const regionOffers = useQuery({ queryKey: ["region-offers", selected, category, includeSimulated], enabled: !!selected,
    queryFn: () => api.get<Offer[]>("/analytics/recent-offers", { region_id: selected!, category_id: category || undefined, include_simulated: includeSimulated, limit: 15 }) });

  const effectiveMode = mode === "price" && !product ? "offers" : mode;
  const points = (stats.data ?? []).map((r) => {
    const pr = prices.data?.find((p) => p.region_id === r.region_id);
    const value = effectiveMode === "price" ? (pr ? Number(pr.avg) : 0) : effectiveMode === "suppliers" ? r.suppliers_registered : r.active_offers;
    const label = effectiveMode === "price" ? (pr ? `${fmtUZS(pr.avg, lang)}/${product?.base_unit.symbol}` : t("regions.noOffers"))
      : effectiveMode === "suppliers" ? t("regions.suppliersN", { n: r.suppliers_registered }) : t("dashboard.offersSuppliers", { o: r.active_offers, s: r.suppliers_with_offers });
    return { id: r.region_id, name: nm(r), lat: r.center_lat, lng: r.center_lng, value, label, selected: r.region_id === selected };
  });
  const sel = stats.data?.find((r) => r.region_id === selected);

  return (
    <div className="space-y-5">
      <PageHeader title={t("regions.title")} description={t("regions.subtitle")}
        actions={<div className="w-56"><CategorySelect value={category} onChange={setCategory} /></div>} />
      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title={t("regions.map")} description={t("regions.mapHint")}
            action={<Tabs value={mode} onChange={setMode} items={[{ value: "offers", label: t("regions.byOffers") }, { value: "suppliers", label: t("regions.bySuppliers") }, { value: "price", label: t("regions.byPrice") }]} />} />
          <CardBody>
            {mode === "price" && <div className="mb-3 max-w-md"><Field label={t("common.product")}><ProductPicker value={product} onChange={setProduct} categoryId={category} /></Field></div>}
            {stats.isLoading ? <LoadingState /> : stats.error ? <ErrorState error={stats.error} /> : <UzMap points={points} onSelect={setSelected} />}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title={sel ? nm(sel) : t("regions.selectRegion")} />
          <CardBody>
            {!sel ? <EmptyState title={t("regions.clickMap")} /> : (
              <div className="space-y-3 text-sm">
                <p>{t("regions.registered")}: <b>{sel.suppliers_registered}</b></p>
                <p>{t("dashboard.activeOffers")}: <b>{sel.active_offers}</b> · {t("regions.withOffers")}: <b>{sel.suppliers_with_offers}</b></p>
                <Link to={`/suppliers?region=${sel.region_id}`} className="text-xs text-primary">{t("regions.seeSuppliers")}</Link>
                {regionOffers.isLoading ? <LoadingState /> : regionOffers.data?.length ? (
                  <ul className="divide-y divide-border">{regionOffers.data.map((o) => (
                    <li key={o.id} className="py-2">
                      <Link to={`/products/${o.product.id}`} className="font-medium hover:text-primary">{o.product.name}</Link>
                      <p className="text-xs text-muted-foreground">{o.supplier.name} · {fmtUZS(o.price_per_base_unit_uzs, lang)}/{o.product.base_unit}</p>
                      <div className="mt-0.5 flex gap-1"><ProvenanceBadge kind={o.provenance_kind} />{o.is_simulated && <SimulatedBadge />}</div>
                    </li>))}</ul>
                ) : <EmptyState title={t("regions.noOffers")} />}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
      <Card>
        <CardHeader title={t("regions.compareProduct")} description={t("regions.compareProductHint")} />
        <CardBody className="space-y-4">
          <div className="max-w-md"><ProductPicker value={product} onChange={setProduct} categoryId={category} /></div>
          {!product ? <EmptyState title={t("analytics.pickProduct")} /> : prices.isLoading ? <LoadingState /> : !prices.data?.length ? <EmptyState title={t("regions.noOffers")} /> : (
            <div className="grid gap-5 lg:grid-cols-2">
              <RegionalBarChart rows={prices.data} unit={product.base_unit.symbol} />
              <div>
                <Table>
                  <thead><tr><Th>{t("common.region")}</Th><Th className="text-right">Min</Th><Th className="text-right">{t("compare.avg")}</Th><Th className="text-right">Max</Th><Th className="text-right">{t("nav.suppliers")}</Th></tr></thead>
                  <tbody>{prices.data.map((r) => (
                    <tr key={r.region_id}><Td>{nm(r)}</Td><Td className="text-right">{fmtNum(r.min, lang)}</Td><Td className="text-right font-medium">{fmtNum(r.avg, lang)}</Td><Td className="text-right">{fmtNum(r.max, lang)}</Td><Td className="text-right">{r.suppliers}</Td></tr>))}</tbody>
                </Table>
                {prices.data.length >= 2 && <Alert tone="blue" className="mt-3">{t("regions.spread", {
                  lo: nm(prices.data[0]), hi: nm(prices.data[prices.data.length - 1]),
                  pct: ((Number(prices.data[prices.data.length - 1].avg) / Number(prices.data[0].avg) - 1) * 100).toFixed(1) })}</Alert>}
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
