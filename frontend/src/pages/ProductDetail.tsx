import { Fragment, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, Bookmark, BookmarkCheck, ChevronDown, ChevronRight, ExternalLink, Info, Pencil, Send, TrendingDown } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCategory } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { ComparedOffer, Comparison, Forecast, History, Observation, Page, Product, RegionalPrice, SupplyDemand } from "@/lib/types";
import { fmtDate, fmtNum, fmtPct, fmtUZS, toNum } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Alert, Badge, Button, Card, CardBody, CardHeader, Dialog, EmptyState, ErrorState, Field, Input, LoadingState, PageHeader,
  Pagination, Switch, Table, Tabs, Td, Textarea, Th } from "@/components/ui";
import { PriceTypeSelect, RegionSelect, UnitSelect } from "@/components/selects";
import { FreshnessBadge, PriceTypeBadge, ProvenanceBadge, SimulatedBadge, VerificationBadge } from "@/components/badges";
import { PriceHistoryChart, RegionalBarChart } from "@/components/charts";
import { ProductFormDialog } from "@/components/ProductForm";

export default function ProductDetail() {
  const { id } = useParams();
  const pid = Number(id);
  const { t, nm, lbl, lang } = useI18n();
  const { user, can } = useAuth();
  const { includeSimulated } = usePrefs();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);

  const product = useQuery({ queryKey: ["product", pid], queryFn: () => api.get<Product>(`/products/${pid}`) });
  const { data: cat } = useCategory(product.data?.category_id);
  const saved = useQuery({ queryKey: ["saved-products"], queryFn: () => api.get<{ product: Product }[]>("/saved/products"), enabled: !!user });
  const isSaved = saved.data?.some((s) => s.product.id === pid);
  const toggleSave = useMutation({
    mutationFn: () => (isSaved ? api.del(`/saved/products/${pid}`) : api.put(`/saved/products/${pid}`)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-products"] }),
  });

  if (product.isLoading) return <LoadingState />;
  if (product.error || !product.data) return <ErrorState error={product.error} onRetry={() => product.refetch()} />;
  const p = product.data;
  const attrDefs = Object.fromEntries((cat?.attributes ?? []).map((a) => [a.id, a]));

  return (
    <div className="space-y-5">
      <PageHeader title={p.name}
        description={[p.category && nm(p.category), p.brand, p.model, p.manufacturer].filter(Boolean).join(" · ")}
        actions={<>
          {p.is_simulated && <SimulatedBadge />}
          {user && <Button variant="outline" onClick={() => toggleSave.mutate()} loading={toggleSave.isPending}>
            {isSaved ? <BookmarkCheck className="h-4 w-4 text-primary" /> : <Bookmark className="h-4 w-4" />}{isSaved ? t("common.saved") : t("common.save")}</Button>}
          {can("catalog.manage") && <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" />{t("common.edit")}</Button>}
        </>} />
      <Card>
        <CardBody className="grid gap-4 text-sm md:grid-cols-4">
          <Info2 label={t("product.baseUnit")} value={`${nm(p.base_unit)} (${p.base_unit.symbol})`} />
          <Info2 label={t("product.origin")} value={`${t(`origin.${p.origin_type}`)}${p.country_of_origin ? ` · ${p.country_of_origin}` : ""}`} />
          <Info2 label="SKU / " value={[p.sku, p.barcode].filter(Boolean).join(" · ") || "—"} labelSuffix={t("product.barcode")} />
          <Info2 label={t("common.updated")} value={fmtDate(p.updated_at, lang)} />
          {p.attributes.map((a) => attrDefs[a.attribute_id] && (
            <Info2 key={a.attribute_id} label={nm(attrDefs[a.attribute_id])}
              value={formatAttr(a.value, attrDefs[a.attribute_id].options.map((o) => ({ v: o.value, l: lbl(o) })), t)} />
          ))}
          {p.description && <p className="text-muted-foreground md:col-span-4">{p.description}</p>}
          {cat?.requires_compliance_note && <Alert className="md:col-span-4">{cat.compliance_note}</Alert>}
        </CardBody>
      </Card>
      <ComparisonSection product={p} includeSimulated={includeSimulated} />
      <div className="grid gap-5 xl:grid-cols-2">
        <RegionalSection product={p} includeSimulated={includeSimulated} />
        <SupplyDemandSection product={p} />
      </div>
      <HistorySection product={p} includeSimulated={includeSimulated} />
      <ObservationsSection product={p} includeSimulated={includeSimulated} />
      <ProductFormDialog open={editing} onClose={() => setEditing(false)} product={p} />
    </div>
  );
}

function Info2({ label, value, labelSuffix }: { label: string; value: string; labelSuffix?: string }) {
  return <div><p className="text-xs text-muted-foreground">{label}{labelSuffix}</p><p className="font-medium">{value}</p></div>;
}

function formatAttr(v: unknown, opts: { v: string; l: string }[], t: (k: string) => string): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? t("common.yes") : t("common.no");
  if (Array.isArray(v)) return v.map((x) => opts.find((o) => o.v === x)?.l ?? String(x)).join(", ");
  const o = opts.find((x) => x.v === String(v));
  return o ? o.l : String(v);
}

function ComparisonSection({ product, includeSimulated }: { product: Product; includeSimulated: boolean }) {
  const { t, lang } = useI18n();
  const { can } = useAuth();
  const [qty, setQty] = useState("");
  const [buyerRegion, setBuyerRegion] = useState<number | "">("");
  const [region, setRegion] = useState<number | "">("");
  const [priceType, setPriceType] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [quoteFor, setQuoteFor] = useState<ComparedOffer | null>(null);
  const params = { quantity: qty && Number(qty) > 0 ? qty : undefined, buyer_region_id: buyerRegion || undefined, region_id: region || undefined,
    price_type: priceType || undefined, verified_only: verifiedOnly || undefined, include_simulated: includeSimulated };
  const cmp = useQuery({ queryKey: ["compare", product.id, params], queryFn: () => api.get<Comparison>(`/products/${product.id}/compare`, params) });
  const unit = product.base_unit.symbol;
  const c = cmp.data;
  const byId = Object.fromEntries((c?.offers ?? []).map((o) => [o.offer_id, o]));
  const cheapest = c?.cheapest_offer_id ? byId[c.cheapest_offer_id] : null;
  const best = c?.best_offer_id ? byId[c.best_offer_id] : null;

  return (
    <Card>
      <CardHeader title={t("compare.title")} description={t("compare.subtitle")} />
      <CardBody className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label={t("compare.quantity", { u: unit })} htmlFor="cmp-qty"><Input id="cmp-qty" type="number" min={0} value={qty} placeholder={t("compare.quantityPh")} onChange={(e) => setQty(e.target.value)} /></Field>
          <Field label={t("compare.deliverTo")}><RegionSelect value={buyerRegion} onChange={setBuyerRegion} allLabel={t("compare.anyDestination")} /></Field>
          <Field label={t("compare.offerRegion")}><RegionSelect value={region} onChange={setRegion} /></Field>
          <Field label={t("common.priceType")}><PriceTypeSelect value={priceType} onChange={setPriceType} /></Field>
          <div className="flex items-end pb-2"><Switch checked={verifiedOnly} onChange={setVerifiedOnly} label={t("compare.verifiedOnly")} /></div>
        </div>
        {cmp.isLoading ? <LoadingState /> : cmp.error ? <ErrorState error={cmp.error} onRetry={() => cmp.refetch()} /> : !c || !c.offers.length ? (
          <EmptyState title={t("compare.noOffers")} description={t("compare.noOffersHint")} />
        ) : (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <HighlightCard tone="teal" icon={<TrendingDown className="h-4 w-4" />} title={t("compare.cheapest")} offer={cheapest} unit={unit} qty={!!params.quantity} />
              <HighlightCard tone="amber" icon={<Award className="h-4 w-4" />} title={t("compare.best")} offer={best} unit={unit} qty={!!params.quantity} showScore />
              <Card className="p-4 text-sm">
                <p className="text-xs text-muted-foreground">{t("compare.marketRange")}</p>
                <p className="mt-1 font-semibold">{fmtUZS(c.summary.min_per_base_unit_uzs, lang)} – {fmtUZS(c.summary.max_per_base_unit_uzs, lang)}</p>
                <p className="text-xs text-muted-foreground">{t("compare.avg")}: {fmtUZS(c.summary.avg_per_base_unit_uzs, lang)}/{unit} · {t("compare.nOffers", { n: c.summary.offers_comparable })}</p>
                {c.summary.simulated_offers > 0 && <p className="mt-2 text-xs text-red-700">{t("compare.simulatedIncluded", { n: c.summary.simulated_offers })}</p>}
              </Card>
            </div>
            <Alert tone="blue">
              <p className="mb-1 flex items-center gap-1 font-medium"><Info className="h-3.5 w-3.5" />{t("compare.howRanked")}</p>
              <ul className="list-disc space-y-0.5 pl-4">{c.explanation.map((e, i) => <li key={i}>{e}</li>)}</ul>
              <p className="mt-1">{t("compare.weights")}: {Object.entries(c.weights as Record<string, number>).map(([k, v]) => `${t(`criteria.${k}`)} ${Math.round(v * 100)}%`).join(" · ")}</p>
            </Alert>
            <Table>
              <thead><tr>
                <Th />
                <Th>{t("common.supplier")}</Th><Th>{t("common.region")}</Th><Th className="text-right">{t("compare.offerPrice")}</Th>
                <Th className="text-right">{t("compare.perUnit", { u: unit })}</Th><Th>MOQ / {t("compare.stock")}</Th><Th>{t("compare.delivery")}</Th>
                {params.quantity && <Th className="text-right">{t("compare.total")}</Th>}<Th className="text-right">{t("compare.score")}</Th>
                <Th>{t("common.source")}</Th><Th />
              </tr></thead>
              <tbody>
                {c.offers.map((o) => (
                  <Fragment key={o.offer_id}>
                    <tr className={cn("hover:bg-slate-50", o.excluded_reason && "opacity-60", o.offer_id === c.best_offer_id && "bg-amber-50/50")}>
                      <Td><button aria-label={t("compare.breakdown")} onClick={() => setOpen(open === o.offer_id ? null : o.offer_id)}>
                        {open === o.offer_id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</button></Td>
                      <Td>
                        <Link to={`/suppliers/${o.supplier.id}`} className="font-medium hover:text-primary">{o.supplier.name}</Link>
                        <div className="mt-1 flex flex-wrap gap-1"><VerificationBadge status={o.supplier.verification_status} />
                          {o.offer_id === c.cheapest_offer_id && <Badge tone="blue">{t("compare.cheapest")}</Badge>}
                          {o.offer_id === c.best_offer_id && <Badge tone="amber">{t("compare.best")}</Badge>}
                          {o.is_featured && <Badge tone="violet">{t("compare.sponsored")}</Badge>}</div>
                      </Td>
                      <Td className="whitespace-nowrap">{lang === "ru" ? o.region.name_ru : o.region.name_uz}
                        {o.delivery.distance_km !== null && o.delivery.distance_km > 0 && <p className="text-xs text-muted-foreground">~{fmtNum(o.delivery.distance_km, lang)} km</p>}</Td>
                      <Td className="whitespace-nowrap text-right">{fmtNum(o.price.original, lang)} {o.price.currency}/{o.price.unit}
                        {o.price.currency !== "UZS" && <p className="text-[11px] text-muted-foreground">{t("compare.rate", { r: fmtNum(o.price.exchange_rate, lang), d: fmtDate(o.price.exchange_rate_at, lang) })}</p>}
                        <div className="mt-0.5"><PriceTypeBadge type={o.price.price_type} /></div></Td>
                      <Td className="whitespace-nowrap text-right font-medium">{fmtUZS(o.price.per_base_unit_uzs, lang)}</Td>
                      <Td className="whitespace-nowrap text-xs">{fmtNum(o.moq, lang)} / {o.available_qty === null ? t("compare.notDeclared") : fmtNum(o.available_qty, lang)} {o.price.unit}
                        {o.stock_status === "insufficient" && <p className="text-red-600">{t("compare.insufficientStock")}</p>}</Td>
                      <Td className="text-xs">{o.delivery.available ? (o.delivery.cost_uzs !== null ? fmtUZS(o.delivery.cost_uzs, lang) : t("compare.costUnknown")) : t("compare.pickup")}
                        {!o.delivery.deliverable_to_buyer && <p className="text-red-600">{t("compare.noDeliveryToRegion")}</p>}</Td>
                      {params.quantity && <Td className="whitespace-nowrap text-right font-medium">{fmtUZS(o.cost.total_uzs, lang)}
                        {o.notes.includes("moq_applied") && <p className="text-[11px] text-amber-700">{t("compare.moqApplied", { n: fmtNum(o.cost.order_units, lang) })}</p>}</Td>}
                      <Td className="text-right">{o.score === null ? <Badge tone="slate">{t(`compare.excluded.${o.excluded_reason}`)}</Badge> : fmtNum(o.score * 100, lang, 1)}</Td>
                      <Td><div className="flex flex-wrap gap-1"><ProvenanceBadge kind={o.provenance.kind} />{o.provenance.is_simulated && <SimulatedBadge />}
                        <FreshnessBadge updatedAt={o.freshness.price_updated_at} thresholdHours={o.freshness.threshold_hours} /></div></Td>
                      <Td>{can("quotes.request") && <Button size="sm" variant="outline" onClick={() => setQuoteFor(o)}><Send className="h-3.5 w-3.5" />{t("compare.requestQuote")}</Button>}</Td>
                    </tr>
                    {open === o.offer_id && (
                      <tr><td colSpan={params.quantity ? 11 : 10} className="border-b border-border bg-slate-50 px-6 py-3">
                        <div className="grid gap-4 text-xs md:grid-cols-3">
                          <div>
                            <p className="mb-1 font-semibold">{t("compare.breakdown")}</p>
                            <table className="w-full"><tbody>{o.score_breakdown.map((b) => (
                              <tr key={b.criterion}><td>{t(`criteria.${b.criterion}`)}</td><td className="text-right">{b.score.toFixed(2)}</td>
                                <td className="text-right text-muted-foreground">× {b.weight}</td><td className="text-right font-medium">{b.contribution.toFixed(3)}</td></tr>))}
                            </tbody></table>
                          </div>
                          <div>
                            <p className="mb-1 font-semibold">{t("compare.costDetail")}</p>
                            <p>{t("compare.goods")}: {fmtUZS(o.cost.goods_uzs, lang)}</p>
                            <p>{t("compare.delivery")}: {fmtUZS(o.cost.delivery_uzs, lang)}</p>
                            <p>{t("compare.fees")}: {fmtUZS(o.cost.fees_uzs, lang)}</p>
                            <p>{t("compare.effective")}: {fmtUZS(o.cost.effective_per_base_unit_uzs, lang)}/{unit}</p>
                            {o.notes.length > 0 && <p className="mt-1 text-amber-700">{o.notes.map((n) => t(`compare.note.${n}`)).join("; ")}</p>}
                          </div>
                          <div>
                            <p className="mb-1 font-semibold">{t("common.provenance")}</p>
                            <p>{t("common.source")}: {o.provenance.source}</p>
                            <p>{t("compare.originalName")}: {o.provenance.original_product_name ?? "—"}</p>
                            <p>{t("compare.verification")}: {t(`verification.${o.provenance.verification_status}`)}</p>
                            <p>{t("common.updated")}: {fmtDate(o.freshness.price_updated_at, lang, true)}</p>
                            {o.provenance.source_url && <a href={o.provenance.source_url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-primary">{t("compare.sourceLink")}<ExternalLink className="h-3 w-3" /></a>}
                          </div>
                        </div>
                      </td></tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </Table>
          </>
        )}
      </CardBody>
      {quoteFor && <QuoteDialog offer={quoteFor} product={product} onClose={() => setQuoteFor(null)} defaultQty={qty} />}
    </Card>
  );
}

function HighlightCard({ title, offer, unit, qty, showScore, icon, tone }: { title: string; offer: ComparedOffer | null; unit: string; qty: boolean; showScore?: boolean; icon: ReactNode; tone: "teal" | "amber" }) {
  const { t, lang } = useI18n();
  return (
    <Card className={cn("p-4", tone === "teal" ? "border-teal-200 bg-teal-50/40" : "border-amber-200 bg-amber-50/40")}>
      <p className="flex items-center gap-1 text-xs font-medium text-muted-foreground">{icon}{title}</p>
      {offer ? (
        <>
          <p className="mt-1 truncate font-semibold">{offer.supplier.name}</p>
          <p className="text-lg font-semibold">{fmtUZS(qty && offer.cost.total_uzs !== null ? offer.cost.total_uzs : offer.price.per_base_unit_uzs, lang)}
            <span className="text-xs font-normal text-muted-foreground">{qty && offer.cost.total_uzs !== null ? ` ${t("compare.totalShort")}` : ` /${unit}`}</span></p>
          {showScore && offer.score !== null && (
            <p className="text-xs text-muted-foreground">{t("compare.score")}: {(offer.score * 100).toFixed(1)} · {t("compare.topFactors")}: {
              [...offer.score_breakdown].sort((a, b) => b.contribution - a.contribution).slice(0, 2).map((b) => t(`criteria.${b.criterion}`)).join(", ")}</p>
          )}
        </>
      ) : <p className="mt-2 text-xs text-muted-foreground">{t("compare.noneEligible")}</p>}
    </Card>
  );
}

function QuoteDialog({ offer, product, onClose, defaultQty }: { offer: ComparedOffer; product: Product; onClose: () => void; defaultQty: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [qty, setQty] = useState(defaultQty || String(toNum(offer.moq) ?? 1));
  const [unitId, setUnitId] = useState<number | "">(product.base_unit.id);
  const [region, setRegion] = useState<number | "">("");
  const [msg, setMsg] = useState("");
  const m = useMutation({
    mutationFn: () => api.post("/quotes", { product_id: product.id, supplier_id: offer.supplier.id, quantity: qty, unit_id: unitId,
      delivery_region_id: region || null, message: msg || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["quotes-sent"] }); },
  });
  return (
    <Dialog open onClose={onClose} title={t("quote.title", { s: offer.supplier.name })}
      footer={m.isSuccess ? <Button onClick={onClose}>{t("common.close")}</Button> : <>
        <Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
        <Button onClick={() => m.mutate()} loading={m.isPending} disabled={!qty || Number(qty) <= 0 || !unitId}>{t("quote.send")}</Button></>}>
      {m.isSuccess ? <Alert tone="green">{t("quote.sent")}</Alert> : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("common.quantity")} htmlFor="q-qty"><Input id="q-qty" type="number" min={0} value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
            <Field label={t("common.unit")}><UnitSelect value={unitId} onChange={setUnitId} /></Field>
          </div>
          <Field label={t("compare.deliverTo")}><RegionSelect value={region} onChange={setRegion} allLabel={t("common.notSpecified")} /></Field>
          <Field label={t("quote.message")} htmlFor="q-msg"><Textarea id="q-msg" value={msg} maxLength={2000} onChange={(e) => setMsg(e.target.value)} /></Field>
          {m.error && <Alert tone="red">{(m.error as Error).message}</Alert>}
        </div>
      )}
    </Dialog>
  );
}

function RegionalSection({ product, includeSimulated }: { product: Product; includeSimulated: boolean }) {
  const { t, nm, lang } = useI18n();
  const q = useQuery({ queryKey: ["regional", product.id, includeSimulated], queryFn: () => api.get<RegionalPrice[]>(`/products/${product.id}/regional`, { include_simulated: includeSimulated }) });
  return (
    <Card>
      <CardHeader title={t("product.regional")} description={t("product.regionalHint", { u: product.base_unit.symbol })} />
      <CardBody>
        {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState /> : (
          <>
            <RegionalBarChart rows={q.data} unit={product.base_unit.symbol} />
            <Table className="mt-3">
              <thead><tr><Th>{t("common.region")}</Th><Th className="text-right">Min</Th><Th className="text-right">{t("compare.avg")}</Th><Th className="text-right">Max</Th><Th className="text-right">{t("nav.suppliers")}</Th></tr></thead>
              <tbody>{q.data.map((r) => (
                <tr key={r.region_id}><Td>{nm(r)}</Td><Td className="text-right">{fmtNum(r.min, lang)}</Td><Td className="text-right font-medium">{fmtNum(r.avg, lang)}</Td>
                  <Td className="text-right">{fmtNum(r.max, lang)}</Td><Td className="text-right">{r.suppliers}</Td></tr>))}</tbody>
            </Table>
          </>
        )}
      </CardBody>
    </Card>
  );
}

function SupplyDemandSection({ product }: { product: Product }) {
  const { t, lang } = useI18n();
  const q = useQuery({ queryKey: ["supply-demand", product.id], queryFn: () => api.get<SupplyDemand>(`/products/${product.id}/supply-demand`) });
  const v = (x: unknown) => (x === "insufficient_data" ? <Badge tone="slate">{t("common.insufficientData")}</Badge> : fmtNum(x as number, lang));
  return (
    <Card>
      <CardHeader title={t("sd.title")} description={q.data ? t("sd.window", { n: q.data.window_days }) : undefined} />
      <CardBody>
        {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : q.data && (
          <div className="space-y-3 text-sm">
            <Row k={t("sd.activeOffers")} v={v(q.data.observed_supply.active_offers)} group={t("sd.observedSupply")} />
            <Row k={t("sd.activeSuppliers")} v={v(q.data.observed_supply.active_suppliers)} group={t("sd.observedSupply")} />
            <Row k={t("sd.declaredStock", { u: product.base_unit.symbol })} v={v(q.data.declared_stock_base_units)} group={t("sd.declared")} />
            <Row k={t("sd.searchInterest")} v={v(q.data.search_interest)} group={t("sd.activity")} />
            <Row k={t("sd.quoteRequests")} v={v(q.data.quote_requests)} group={t("sd.activity")} />
            <Row k={t("sd.transactions")} v={v(q.data.completed_transactions)} group={t("sd.transactionsGroup")} />
            <Row k={t("sd.estimatedDemand")} v={v(q.data.estimated_demand)} group={t("sd.estimate")} />
            <Alert tone="amber">{t("sd.note")}</Alert>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function Row({ k, v, group }: { k: string; v: ReactNode; group: string }) {
  return <div className="flex items-center justify-between gap-2 border-b border-border pb-2 last:border-0">
    <div><p>{k}</p><p className="text-[11px] text-muted-foreground">{group}</p></div><div className="font-medium">{v}</div></div>;
}

function HistorySection({ product, includeSimulated }: { product: Product; includeSimulated: boolean }) {
  const { t, lang } = useI18n();
  const [gran, setGran] = useState<"day" | "week" | "month">("week");
  const [region, setRegion] = useState<number | "">("");
  const [days, setDays] = useState(180);
  const [showForecast, setShowForecast] = useState(false);
  const params = { granularity: gran, region_id: region || undefined, days, include_simulated: includeSimulated };
  const h = useQuery({ queryKey: ["history", product.id, params], queryFn: () => api.get<History>(`/products/${product.id}/history`, params) });
  const f = useQuery({ queryKey: ["forecast", product.id, region], queryFn: () => api.get<Forecast>(`/products/${product.id}/forecast`, { region_id: region || undefined }), enabled: showForecast });
  return (
    <Card>
      <CardHeader title={t("history.title")} description={t("history.subtitle", { u: product.base_unit.symbol })}
        action={<div className="flex flex-wrap items-center gap-2">
          <Tabs value={gran} onChange={setGran} items={[{ value: "day", label: t("history.day") }, { value: "week", label: t("history.week") }, { value: "month", label: t("history.month") }]} />
          <select className="h-8 rounded-md border border-border px-2 text-xs" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label={t("history.range")}>
            {[30, 90, 180, 365].map((d) => <option key={d} value={d}>{t("history.lastDays", { n: d })}</option>)}
          </select>
          <div className="w-44"><RegionSelect value={region} onChange={setRegion} /></div>
          <Switch checked={showForecast} onChange={setShowForecast} label={t("history.forecast")} />
        </div>} />
      <CardBody>
        {h.isLoading ? <LoadingState /> : h.error ? <ErrorState error={h.error} /> : !h.data || h.data.status !== "ok" ? (
          <EmptyState title={t("common.insufficientData")} description={t("history.noData")} />
        ) : (
          <>
            <div className="mb-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
              <span>{t("history.change")}: <b className={cn((h.data.change_pct ?? 0) > 0 ? "text-red-600" : "text-emerald-600")}>{fmtPct(h.data.change_pct)}</b></span>
              <span>{t("history.observations")}: <b>{fmtNum(h.data.observations, lang)}</b></span>
              <span>{fmtDate(h.data.first_observed_at, lang)} – {fmtDate(h.data.last_observed_at, lang)}</span>
              {Object.entries(h.data.provenance_breakdown ?? {}).map(([k, n]) => <span key={k}><ProvenanceBadge kind={k} /> {n}</span>)}
            </div>
            <PriceHistoryChart points={h.data.points} forecast={showForecast ? f.data : undefined} unit={product.base_unit.symbol} />
            {showForecast && f.data && (f.data.status === "ok"
              ? <Alert className="mt-2">{t("history.forecastNote")} {f.data.method}. {(h.data.simulated_share ?? 0) > 0 && t("history.forecastSim")}</Alert>
              : <Alert tone="blue" className="mt-2">{t("history.forecastInsufficient", { a: f.data.available_weeks ?? 0, r: f.data.required_weeks ?? 0 })}</Alert>)}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function ObservationsSection({ product, includeSimulated }: { product: Product; includeSimulated: boolean }) {
  const { t, nm, lang } = useI18n();
  const [page, setPage] = useState(1);
  const q = useQuery({ queryKey: ["observations", product.id, page, includeSimulated],
    queryFn: () => api.get<Page<Observation>>(`/products/${product.id}/observations`, { page, page_size: 10, include_simulated: includeSimulated }) });
  return (
    <Card>
      <CardHeader title={t("obs.title")} description={t("obs.subtitle")} />
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState /> : (
        <div className="px-2">
          <Table>
            <thead><tr><Th>{t("obs.observed")}</Th><Th>{t("common.supplier")}</Th><Th>{t("common.region")}</Th><Th className="text-right">{t("obs.original")}</Th>
              <Th className="text-right">{t("obs.normalized", { u: product.base_unit.symbol })}</Th><Th>{t("common.provenance")}</Th><Th>{t("obs.method")}</Th><Th>{t("obs.quality")}</Th></tr></thead>
            <tbody>{q.data.items.map((o) => (
              <tr key={o.id}>
                <Td className="whitespace-nowrap text-xs">{fmtDate(o.observed_at, lang, true)}<p className="text-muted-foreground">{t("obs.collected")}: {fmtDate(o.collected_at, lang)}</p></Td>
                <Td className="text-xs">{o.supplier_name ?? "—"}<p className="text-muted-foreground">{o.original_product_name}</p></Td>
                <Td className="text-xs">{nm(o.region)}</Td>
                <Td className="whitespace-nowrap text-right text-xs">{fmtNum(o.original_price, lang)} {o.original_currency}/{o.original_unit_text}</Td>
                <Td className="whitespace-nowrap text-right font-medium">{fmtNum(o.normalized_price_uzs, lang)}</Td>
                <Td><div className="flex flex-wrap gap-1"><ProvenanceBadge kind={o.provenance_kind} />{o.is_simulated && <SimulatedBadge />}<VerificationBadge status={o.verification_status} /></div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{o.data_source?.name}</p></Td>
                <Td className="text-xs">{t(`method.${o.collection_method}`)}{o.source_url && <a href={o.source_url} target="_blank" rel="noopener noreferrer nofollow" className="ml-1 text-primary"><ExternalLink className="inline h-3 w-3" /></a>}</Td>
                <Td className="text-xs">{fmtNum(o.quality_score, lang, 2)}{o.is_outlier && <Badge tone="red" className="ml-1">{t("obs.outlier")}</Badge>}</Td>
              </tr>))}</tbody>
          </Table>
          <Pagination page={page} pageSize={10} total={q.data.total} onPage={setPage} />
        </div>
      )}
    </Card>
  );
}
