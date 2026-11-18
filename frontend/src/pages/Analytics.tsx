import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { Forecast, History, Movers, Product } from "@/lib/types";
import { fmtDate, fmtNum, fmtPct } from "@/lib/format";
import { Alert, Badge, Card, CardBody, CardHeader, EmptyState, ErrorState, Field, LoadingState, PageHeader, Switch, Table, Tabs, Td, Th } from "@/components/ui";
import { CategorySelect, PriceTypeSelect, RegionSelect } from "@/components/selects";
import { PriceHistoryChart } from "@/components/charts";
import { ProductPicker } from "@/components/ProductPicker";

interface Anomaly { observation_id: number; product_id: number; product_name: string | null; region_id: number; observed_at: string;
  price: number; median: number; robust_z: number; isolation_forest_flag: boolean; direction: string; is_simulated: boolean }

export default function Analytics() {
  const { t, lang } = useI18n();
  const { can } = useAuth();
  const { includeSimulated } = usePrefs();
  const [category, setCategory] = useState<number | "">("");
  const [region, setRegion] = useState<number | "">("");
  const params = { category_id: category || undefined, region_id: region || undefined, include_simulated: includeSimulated, limit: 15 };
  const movers = useQuery({ queryKey: ["movers-full", params], queryFn: () => api.get<Movers>("/analytics/movers", params) });
  const anomalies = useQuery({ queryKey: ["anomalies", category, includeSimulated], enabled: can("market_data.manage"),
    queryFn: () => api.get<{ status: string; method?: string; anomalies: Anomaly[] }>("/analytics/anomalies", { category_id: category || undefined, include_simulated: includeSimulated }) });

  return (
    <div className="space-y-5">
      <PageHeader title={t("analytics.title")} description={t("analytics.subtitle")}
        actions={<><div className="w-48"><CategorySelect value={category} onChange={setCategory} /></div><div className="w-48"><RegionSelect value={region} onChange={setRegion} /></div></>} />
      <ProductExplorer includeSimulated={includeSimulated} category={category} />
      <Card>
        <CardHeader title={t("analytics.movers")} description={movers.data?.method} />
        <CardBody className="grid gap-5 lg:grid-cols-2">
          {movers.isLoading ? <LoadingState /> : movers.error ? <ErrorState error={movers.error} /> : (["increases", "decreases"] as const).map((k) => (
            <div key={k}>
              <p className="mb-2 text-sm font-medium">{t(`dashboard.${k}`)}</p>
              {movers.data?.[k].length ? (
                <Table>
                  <thead><tr><Th>{t("common.product")}</Th><Th className="text-right">{t("analytics.prev")}</Th><Th className="text-right">{t("analytics.current")}</Th><Th className="text-right">Δ</Th></tr></thead>
                  <tbody>{movers.data[k].map((m) => (
                    <tr key={m.product_id}><Td><Link to={`/products/${m.product_id}`} className="hover:text-primary">{m.name}</Link></Td>
                      <Td className="text-right">{fmtNum(m.prev_avg, lang)}</Td><Td className="text-right">{fmtNum(m.current_avg, lang)}</Td>
                      <Td className={k === "increases" ? "text-right text-red-600" : "text-right text-emerald-600"}>{fmtPct(m.change_pct)}</Td></tr>))}</tbody>
                </Table>
              ) : <EmptyState title={t("common.insufficientData")} description={t("analytics.noMovers", { th: movers.data?.threshold_pct ?? "", w: movers.data?.window_days ?? "" })} />}
            </div>
          ))}
        </CardBody>
      </Card>
      {can("market_data.manage") && (
        <Card>
          <CardHeader title={t("analytics.anomalies")} description={anomalies.data?.method} />
          {anomalies.isLoading ? <LoadingState /> : anomalies.error ? <ErrorState error={anomalies.error} /> : !anomalies.data?.anomalies.length ? <EmptyState title={t("analytics.noAnomalies")} /> : (
            <Table>
              <thead><tr><Th>{t("common.product")}</Th><Th>{t("obs.observed")}</Th><Th className="text-right">{t("analytics.price")}</Th><Th className="text-right">{t("analytics.median")}</Th>
                <Th className="text-right">z</Th><Th>IsolationForest</Th><Th /></tr></thead>
              <tbody>{anomalies.data.anomalies.map((a) => (
                <tr key={a.observation_id}><Td><Link to={`/products/${a.product_id}`} className="hover:text-primary">{a.product_name}</Link></Td>
                  <Td className="text-xs">{fmtDate(a.observed_at, lang)}</Td><Td className="text-right">{fmtNum(a.price, lang)}</Td><Td className="text-right">{fmtNum(a.median, lang)}</Td>
                  <Td className="text-right">{a.robust_z.toFixed(1)}</Td><Td>{a.isolation_forest_flag ? <Badge tone="red">✓</Badge> : "—"}</Td>
                  <Td>{a.is_simulated && <Badge tone="red">{t("simulated.badge")}</Badge>}</Td></tr>))}</tbody>
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}

function ProductExplorer({ includeSimulated, category }: { includeSimulated: boolean; category: number | "" }) {
  const { t, lang } = useI18n();
  const [product, setProduct] = useState<Product | null>(null);
  const [gran, setGran] = useState<"day" | "week" | "month">("week");
  const [region, setRegion] = useState<number | "">("");
  const [priceType, setPriceType] = useState("");
  const [days, setDays] = useState(180);
  const [fc, setFc] = useState(false);
  const params = { granularity: gran, region_id: region || undefined, include_simulated: includeSimulated, price_type: priceType || undefined, days };
  const h = useQuery({ queryKey: ["history", product?.id, params], enabled: !!product,
    queryFn: () => api.get<History>(`/products/${product!.id}/history`, params) });
  const f = useQuery({ queryKey: ["forecast", product?.id, region], enabled: !!product && fc,
    queryFn: () => api.get<Forecast>(`/products/${product!.id}/forecast`, { region_id: region || undefined }) });
  return (
    <Card>
      <CardHeader title={t("analytics.explorer")} description={t("analytics.explorerHint")} />
      <CardBody className="space-y-4">
        <div className="grid gap-3 md:grid-cols-5">
          <div className="md:col-span-2"><Field label={t("common.product")}><ProductPicker value={product} onChange={setProduct} categoryId={category} /></Field></div>
          <Field label={t("common.region")}><RegionSelect value={region} onChange={setRegion} /></Field>
          <Field label={t("common.priceType")}><PriceTypeSelect value={priceType} onChange={setPriceType} /></Field>
          <Field label={t("history.range")}>
            <select className="h-9 w-full rounded-md border border-border px-2 text-sm" value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {[30, 90, 180, 365].map((d) => <option key={d} value={d}>{t("history.lastDays", { n: d })}</option>)}
            </select>
          </Field>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Tabs value={gran} onChange={setGran} items={[{ value: "day", label: t("history.day") }, { value: "week", label: t("history.week") }, { value: "month", label: t("history.month") }]} />
          <Switch checked={fc} onChange={setFc} label={t("history.forecast")} />
          {product && <Link to={`/products/${product.id}`} className="text-xs text-primary">{t("analytics.openProduct")}</Link>}
        </div>
        {!product ? <EmptyState title={t("analytics.pickProduct")} /> : h.isLoading ? <LoadingState /> : h.error ? <ErrorState error={h.error} /> :
          h.data?.status !== "ok" ? <EmptyState title={t("common.insufficientData")} /> : (
            <>
              <p className="text-xs text-muted-foreground">{t("history.change")}: <b>{fmtPct(h.data.change_pct)}</b> · {t("history.observations")}: {fmtNum(h.data.observations, lang)} · UZS/{h.data.base_unit}</p>
              <PriceHistoryChart points={h.data.points} forecast={fc ? f.data : undefined} unit={h.data.base_unit ?? ""} />
              {fc && f.data && f.data.status !== "ok" && <Alert tone="blue">{t("history.forecastInsufficient", { a: f.data.available_weeks ?? 0, r: f.data.required_weeks ?? 0 })}</Alert>}
              {fc && f.data?.status === "ok" && <Alert>{t("history.forecastNote")} {f.data.method}.</Alert>}
            </>
          )}
      </CardBody>
    </Card>
  );
}
