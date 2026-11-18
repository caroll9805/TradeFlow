import { useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, Search, SlidersHorizontal } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCategories, useCategory } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { Page, Product } from "@/lib/types";
import { fmtDate, fmtUZS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, LoadingState, PageHeader, Pagination, Select } from "@/components/ui";
import { PriceTypeSelect, RegionSelect } from "@/components/selects";
import { SimulatedBadge } from "@/components/badges";
import { AttributeInput, ProductFormDialog } from "@/components/ProductForm";

export default function Catalog() {
  const { t, nm, lang } = useI18n();
  const { can } = useAuth();
  const { includeSimulated } = usePrefs();
  const [sp, setSp] = useSearchParams();
  const category = sp.get("category") ? Number(sp.get("category")) : "";
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [region, setRegion] = useState<number | "">("");
  const [priceType, setPriceType] = useState("");
  const [brand, setBrand] = useState("");
  const [origin, setOrigin] = useState("");
  const [pmin, setPmin] = useState("");
  const [pmax, setPmax] = useState("");
  const [hasOffers, setHasOffers] = useState(false);
  const [sort, setSort] = useState("offers");
  const [attrs, setAttrs] = useState<Record<number, unknown>>({});
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);
  const [adding, setAdding] = useState(false);
  const { data: cats } = useCategories();
  const { data: cat } = useCategory(category || null);
  const { data: brands } = useQuery({ queryKey: ["brands", category], queryFn: () => api.get<string[]>("/products/brands", { category_id: category || undefined }) });

  const attrFilter = useMemo(() => {
    const e = Object.entries(attrs).filter(([, v]) => v !== null && v !== "" && v !== undefined);
    return e.length ? JSON.stringify(Object.fromEntries(e)) : undefined;
  }, [attrs]);
  const params = { q: sp.get("q") || undefined, category_id: category || undefined, region_id: region || undefined,
    price_type: priceType || undefined, brand: brand || undefined, origin_type: origin || undefined, price_min: pmin || undefined,
    price_max: pmax || undefined, has_offers: hasOffers || undefined, include_simulated: includeSimulated, sort, attrs: attrFilter,
    page, page_size: 20 };
  const res = useQuery({ queryKey: ["products", params], queryFn: () => api.get<Page<Product>>("/products", params), placeholderData: keepPreviousData });

  const setCategory = (id: number | "") => {
    const n = new URLSearchParams(sp);
    if (id) n.set("category", String(id)); else n.delete("category");
    setSp(n); setAttrs({}); setBrand(""); setPage(1);
  };
  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    const n = new URLSearchParams(sp);
    if (q.trim()) n.set("q", q.trim()); else n.delete("q");
    setSp(n); setPage(1);
  };

  return (
    <div>
      <PageHeader title={t("catalog.title")} description={t("catalog.subtitle")}
        actions={can("products.create") && <Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" />{t("product.add")}</Button>} />
      <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label={t("common.category")}>
        <button onClick={() => setCategory("")} className={cn("rounded-full border px-3 py-1 text-xs", !category ? "border-primary bg-primary text-white" : "border-border bg-white hover:border-primary")}>{t("common.allCategories")}</button>
        {cats?.map((c) => (
          <button key={c.id} onClick={() => setCategory(c.id)} aria-pressed={category === c.id}
            className={cn("rounded-full border px-3 py-1 text-xs", category === c.id ? "border-primary bg-primary text-white" : "border-border bg-white hover:border-primary")}>{nm(c)}</button>
        ))}
      </div>
      <Card className="mb-4 p-4">
        <form onSubmit={submitSearch} className="flex flex-wrap gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input aria-label={t("catalog.searchPlaceholder")} placeholder={t("catalog.searchPlaceholder")} className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="w-44"><RegionSelect value={region} onChange={(v) => { setRegion(v); setPage(1); }} /></div>
          <Button type="submit">{t("common.search")}</Button>
          <Button variant="outline" onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}><SlidersHorizontal className="h-4 w-4" />{t("catalog.filters")}</Button>
        </form>
        {showFilters && (
          <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label={t("common.priceType")}><PriceTypeSelect value={priceType} onChange={(v) => { setPriceType(v); setPage(1); }} /></Field>
            <Field label={t("product.brand")}>
              <Select value={brand} onChange={(e) => { setBrand(e.target.value); setPage(1); }}>
                <option value="">{t("common.all")}</option>{brands?.map((b) => <option key={b} value={b}>{b}</option>)}
              </Select>
            </Field>
            <Field label={t("product.origin")}>
              <Select value={origin} onChange={(e) => { setOrigin(e.target.value); setPage(1); }}>
                <option value="">{t("common.all")}</option>{["domestic", "import", "unknown"].map((o) => <option key={o} value={o}>{t(`origin.${o}`)}</option>)}
              </Select>
            </Field>
            <Field label={t("catalog.sort")}>
              <Select value={sort} onChange={(e) => setSort(e.target.value)}>
                {["offers", "price_asc", "price_desc", "updated", "name"].map((s) => <option key={s} value={s}>{t(`catalog.sort.${s}`)}</option>)}
              </Select>
            </Field>
            <Field label={t("catalog.minPrice")}><Input type="number" min={0} value={pmin} onChange={(e) => { setPmin(e.target.value); setPage(1); }} /></Field>
            <Field label={t("catalog.maxPrice")}><Input type="number" min={0} value={pmax} onChange={(e) => { setPmax(e.target.value); setPage(1); }} /></Field>
            <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={hasOffers} onChange={(e) => { setHasOffers(e.target.checked); setPage(1); }} />{t("catalog.onlyWithOffers")}</label>
            {cat?.attributes?.filter((a) => a.is_filterable).map((a) => (
              <Field key={a.id} label={nm(a)} htmlFor={`attr-${a.id}`}>
                <AttributeInput a={a.data_type === "multiselect" ? { ...a, data_type: "select" } : a} value={attrs[a.id]} onChange={(v) => { setAttrs({ ...attrs, [a.id]: v }); setPage(1); }} />
              </Field>
            ))}
          </div>
        )}
      </Card>
      {cat?.requires_compliance_note && <p className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">{cat.compliance_note}</p>}

      {res.isLoading ? <LoadingState /> : res.error ? <ErrorState error={res.error} onRetry={() => res.refetch()} /> : !res.data?.items.length ? (
        <Card><EmptyState title={t("catalog.noResults")} description={t("catalog.noResultsHint")} /></Card>
      ) : (
        <>
          <p className="mb-2 text-xs text-muted-foreground">{t("catalog.found", { n: res.data.total })}</p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {res.data.items.map((p) => (
              <Link key={p.id} to={`/products/${p.id}`} className="group">
                <Card className="h-full p-4 transition-shadow group-hover:shadow-md">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[11px] text-muted-foreground">{p.category && nm(p.category)}</p>
                      <h3 className="truncate text-sm font-semibold group-hover:text-primary">{p.name}</h3>
                      <p className="text-xs text-muted-foreground">{[p.brand, p.model].filter(Boolean).join(" · ") || " "}</p>
                    </div>
                    {p.is_simulated && <SimulatedBadge />}
                  </div>
                  <div className="mt-3 flex items-end justify-between">
                    <div>
                      <p className="text-[11px] text-muted-foreground">{t("catalog.fromPrice")}</p>
                      <p className="text-lg font-semibold">{p.offer_stats?.offers ? fmtUZS(p.offer_stats.min_per_base_unit_uzs, lang) : "—"}
                        <span className="text-xs font-normal text-muted-foreground"> /{p.base_unit.symbol}</span></p>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      <Badge tone={p.offer_stats?.offers ? "blue" : "slate"}>{t("catalog.offersN", { n: p.offer_stats?.offers ?? 0 })}</Badge>
                      <p className="mt-1">{t("catalog.regionsN", { n: p.offer_stats?.regions ?? 0 })}</p>
                    </div>
                  </div>
                  {p.offer_stats?.last_updated && <p className="mt-2 text-[11px] text-muted-foreground">{t("common.updated")}: {fmtDate(p.offer_stats.last_updated, lang)}</p>}
                </Card>
              </Link>
            ))}
          </div>
          <Pagination page={page} pageSize={20} total={res.data.total} onPage={setPage} />
        </>
      )}
      <ProductFormDialog open={adding} onClose={() => setAdding(false)} />
    </div>
  );
}
