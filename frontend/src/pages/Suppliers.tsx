import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search, Star } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { Page, SupplierLite } from "@/lib/types";
import { fmtNum } from "@/lib/format";
import { Badge, Card, EmptyState, ErrorState, Input, LoadingState, PageHeader, Pagination, Select, Switch } from "@/components/ui";
import { CategorySelect, RegionSelect } from "@/components/selects";
import { SimulatedBadge, VerificationBadge } from "@/components/badges";

export default function Suppliers() {
  const { t, nm, lang } = useI18n();
  const { includeSimulated } = usePrefs();
  const [q, setQ] = useState("");
  const [sp] = useSearchParams();
  const [region, setRegion] = useState<number | "">(sp.get("region") ? Number(sp.get("region")) : "");
  const [category, setCategory] = useState<number | "">("");
  const [type, setType] = useState("");
  const [verified, setVerified] = useState(false);
  const [sort, setSort] = useState("offers");
  const [page, setPage] = useState(1);
  const params = { q: q || undefined, region_id: region || undefined, category_id: category || undefined, supplier_type: type || undefined,
    verified_only: verified || undefined, include_simulated: includeSimulated, sort, page, page_size: 24 };
  const res = useQuery({ queryKey: ["suppliers", params], queryFn: () => api.get<Page<SupplierLite>>("/suppliers", params), placeholderData: keepPreviousData });
  const reset = <T,>(fn: (v: T) => void) => (v: T) => { fn(v); setPage(1); };

  return (
    <div>
      <PageHeader title={t("suppliers.title")} description={t("suppliers.subtitle")} />
      <Card className="mb-4 grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-6">
        <div className="relative lg:col-span-2">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input className="pl-9" placeholder={t("suppliers.search")} aria-label={t("suppliers.search")} value={q} onChange={(e) => reset(setQ)(e.target.value)} />
        </div>
        <RegionSelect value={region} onChange={reset(setRegion)} />
        <CategorySelect value={category} onChange={reset(setCategory)} />
        <Select value={type} onChange={(e) => reset(setType)(e.target.value)} aria-label={t("supplier.type")}>
          <option value="">{t("suppliers.allTypes")}</option>
          {["manufacturer", "wholesaler", "distributor", "importer", "retail", "other"].map((s) => <option key={s} value={s}>{t(`supplierType.${s}`)}</option>)}
        </Select>
        <Select value={sort} onChange={(e) => setSort(e.target.value)} aria-label={t("catalog.sort")}>
          {["offers", "rating", "name"].map((s) => <option key={s} value={s}>{t(`suppliers.sort.${s}`)}</option>)}
        </Select>
        <div className="lg:col-span-6"><Switch checked={verified} onChange={reset(setVerified)} label={t("compare.verifiedOnly")} /></div>
      </Card>
      {res.isLoading ? <LoadingState /> : res.error ? <ErrorState error={res.error} onRetry={() => res.refetch()} /> : !res.data?.items.length ? <Card><EmptyState /></Card> : (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {res.data.items.map((s) => (
              <Link key={s.id} to={`/suppliers/${s.id}`} className="group">
                <Card className="h-full p-4 transition-shadow group-hover:shadow-md">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold group-hover:text-primary">{s.name}</h3>
                    {s.is_simulated && <SimulatedBadge />}
                  </div>
                  <p className="text-xs text-muted-foreground">{t(`supplierType.${s.supplier_type}`)} · {s.region ? nm(s.region) : "—"}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-1">
                    <VerificationBadge status={s.verification_status} />
                    <Badge tone="blue">{t("catalog.offersN", { n: s.active_offers ?? 0 })}</Badge>
                    {s.rating_avg !== null && <Badge tone="amber"><Star className="h-3 w-3" />{fmtNum(s.rating_avg, lang, 1)} ({s.rating_count})</Badge>}
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{s.categories.map((c) => nm(c)).join(" · ")}</p>
                </Card>
              </Link>
            ))}
          </div>
          <Pagination page={page} pageSize={24} total={res.data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
