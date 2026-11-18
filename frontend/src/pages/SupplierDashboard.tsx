import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useUnits } from "@/lib/hooks";
import type { Offer, Product, Quote, SupplierDetail } from "@/lib/types";
import { fmtDate, fmtNum, fmtUZS } from "@/lib/format";
import { Alert, Button, Card, CardBody, CardHeader, ConfirmDialog, Dialog, EmptyState, ErrorState, Field, Input, LoadingState, PageHeader,
  Select, Switch, Table, Tabs, Td, Textarea, Th } from "@/components/ui";
import { CategorySelect, RegionSelect, UnitSelect } from "@/components/selects";
import { ProvenanceBadge, VerificationBadge } from "@/components/badges";
import { ProductPicker } from "@/components/ProductPicker";
import { ProductFormDialog } from "@/components/ProductForm";
import { QuoteStatus } from "@/pages/Procurement";

export default function SupplierDashboard() {
  const { t } = useI18n();
  const [tab, setTab] = useState<"offers" | "quotes" | "profile">("offers");
  const mine = useQuery({ queryKey: ["my-suppliers"], queryFn: () => api.get<SupplierDetail[]>("/suppliers/mine") });
  const [supplierId, setSupplierId] = useState<number | null>(null);
  useEffect(() => { if (!supplierId && mine.data?.length) setSupplierId(mine.data[0].id); }, [mine.data, supplierId]);
  const supplier = mine.data?.find((s) => s.id === supplierId) ?? null;

  if (mine.isLoading) return <LoadingState />;
  if (mine.error) return <ErrorState error={mine.error} onRetry={() => mine.refetch()} />;
  return (
    <div className="space-y-5">
      <PageHeader title={t("supplierDash.title")} description={t("supplierDash.subtitle")}
        actions={mine.data && mine.data.length > 1 && (
          <Select value={supplierId ?? ""} onChange={(e) => setSupplierId(Number(e.target.value))} aria-label={t("common.supplier")}>
            {mine.data.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>)} />
      {!supplier ? <Card><EmptyState title={t("supplierDash.noProfile")} action={<ProfileButton />} /></Card> : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Tabs value={tab} onChange={setTab} items={[{ value: "offers", label: t("supplierDash.offers") }, { value: "quotes", label: t("supplierDash.quotes") }, { value: "profile", label: t("supplierDash.profile") }]} />
            <VerificationBadge status={supplier.verification_status} />
          </div>
          {tab === "offers" && <OffersTab supplier={supplier} />}
          {tab === "quotes" && <QuotesTab />}
          {tab === "profile" && <ProfileTab supplier={supplier} />}
        </>
      )}
    </div>
  );
}

function ProfileButton() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return <><Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />{t("supplierDash.createProfile")}</Button>
    {open && <ProfileDialog onClose={() => setOpen(false)} />}</>;
}

function OffersTab({ supplier }: { supplier: SupplierDetail }) {
  const { t, nm, lang } = useI18n();
  const qc = useQueryClient();
  const offers = useQuery({ queryKey: ["my-offers"], queryFn: () => api.get<Offer[]>("/offers/mine") });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Offer | null>(null);
  const [deactivating, setDeactivating] = useState<Offer | null>(null);
  const deactivate = useMutation({ mutationFn: (id: number) => api.del(`/offers/${id}`),
    onSuccess: () => { setDeactivating(null); qc.invalidateQueries({ queryKey: ["my-offers"] }); } });
  const list = offers.data?.filter((o) => o.supplier.id === supplier.id) ?? [];
  return (
    <Card>
      <CardHeader title={t("supplierDash.offers")} description={t("supplierDash.offersHint")}
        action={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" />{t("supplierDash.newOffer")}</Button>} />
      {offers.isLoading ? <LoadingState /> : offers.error ? <ErrorState error={offers.error} /> : !list.length ? <EmptyState description={t("supplierDash.noOffers")} /> : (
        <Table>
          <thead><tr><Th>{t("common.product")}</Th><Th className="text-right">{t("compare.offerPrice")}</Th><Th className="text-right">{t("common.pricePerUnit")}</Th>
            <Th>MOQ / {t("compare.stock")}</Th><Th>{t("common.region")}</Th><Th>{t("common.status")}</Th><Th>{t("common.updated")}</Th><Th /></tr></thead>
          <tbody>{list.map((o) => (
            <tr key={o.id} className={o.is_active ? "" : "opacity-60"}>
              <Td><Link to={`/products/${o.product.id}`} className="font-medium hover:text-primary">{o.product.name}</Link><div className="mt-0.5"><ProvenanceBadge kind={o.provenance_kind} /></div></Td>
              <Td className="whitespace-nowrap text-right">{fmtNum(o.original_price, lang)} {o.original_currency}/{o.unit.symbol}</Td>
              <Td className="whitespace-nowrap text-right">{fmtUZS(o.price_per_base_unit_uzs, lang)}/{o.product.base_unit}</Td>
              <Td className="text-xs">{fmtNum(o.moq, lang)} / {o.available_qty === null ? "—" : fmtNum(o.available_qty, lang)}</Td>
              <Td>{nm(o.region)}</Td>
              <Td>{o.is_active ? t("supplierDash.active") : t("supplierDash.inactive")}</Td>
              <Td className="text-xs">{fmtDate(o.price_updated_at, lang, true)}</Td>
              <Td className="whitespace-nowrap">
                <Button size="sm" variant="ghost" onClick={() => setEditing(o)} aria-label={t("common.edit")}><Pencil className="h-3.5 w-3.5" /></Button>
                {o.is_active && <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDeactivating(o)}>{t("supplierDash.deactivate")}</Button>}
              </Td>
            </tr>))}</tbody>
        </Table>
      )}
      {creating && <OfferDialog supplier={supplier} onClose={() => setCreating(false)} />}
      {editing && <OfferDialog supplier={supplier} offer={editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog open={!!deactivating} destructive title={t("supplierDash.deactivateTitle")} message={t("supplierDash.deactivateMsg", { p: deactivating?.product.name ?? "" })}
        onCancel={() => setDeactivating(null)} onConfirm={() => deactivating && deactivate.mutate(deactivating.id)} loading={deactivate.isPending} />
    </Card>
  );
}

function OfferDialog({ supplier, offer, onClose }: { supplier: SupplierDetail; offer?: Offer; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data: units } = useUnits();
  const [product, setProduct] = useState<Product | null>(null);
  const [newProduct, setNewProduct] = useState(false);
  const [f, setF] = useState({
    price: offer ? String(offer.original_price) : "", currency: offer?.original_currency ?? "UZS", unit_id: offer?.unit.id ?? ("" as number | ""),
    moq: offer?.moq != null ? String(offer.moq) : "", available_qty: offer?.available_qty != null ? String(offer.available_qty) : "",
    region_id: offer?.region.id ?? supplier.region?.id ?? ("" as number | ""), price_type: offer?.price_type ?? "wholesale",
    delivery_available: offer?.delivery_available ?? false, delivery_cost_uzs: offer?.delivery_cost_uzs != null ? String(offer.delivery_cost_uzs) : "",
    valid_until: offer?.valid_until?.slice(0, 10) ?? "", source_url: offer?.source_url ?? "",
  });
  const n = (v: string) => (v === "" ? null : v);
  const save = useMutation({
    mutationFn: () => {
      const common = { moq: n(f.moq), available_qty: n(f.available_qty), delivery_available: f.delivery_available,
        delivery_cost_uzs: f.delivery_available ? n(f.delivery_cost_uzs) : null, valid_until: f.valid_until ? `${f.valid_until}T23:59:59+05:00` : null };
      if (offer) return api.patch<Offer>(`/offers/${offer.id}`, { ...common, price: f.price, currency: f.currency, unit_id: f.unit_id });
      return api.post<Offer>("/offers", { ...common, supplier_id: supplier.id, product_id: product?.id, price: f.price, currency: f.currency,
        unit_id: f.unit_id, region_id: f.region_id, price_type: f.price_type, source_url: n(f.source_url) });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-offers"] }); onClose(); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const baseUnit = offer ? offer.product.base_unit : product?.base_unit.code;
  const unitHint = baseUnit && f.unit_id && units?.find((u) => u.id === f.unit_id)?.code !== baseUnit ? t("supplierDash.unitHint", { u: baseUnit }) : undefined;
  return (
    <Dialog open onClose={onClose} wide title={offer ? t("supplierDash.editOffer", { p: offer.product.name }) : t("supplierDash.newOffer")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
        <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!f.price || !f.unit_id || (!offer && (!product || !f.region_id))}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        {!offer && <div className="md:col-span-2">
          <Field label={t("common.product") + " *"} hint={product ? `${t("product.baseUnit")}: ${product.base_unit.symbol}` : undefined}><ProductPicker value={product} onChange={setProduct} /></Field>
          <button type="button" className="mt-1 text-xs text-primary" onClick={() => setNewProduct(true)}>{t("supplierDash.productMissing")}</button>
        </div>}
        <Field label={t("supplierDash.price") + " *"} htmlFor="o-price"><Input id="o-price" type="number" min={0} step="any" value={f.price} onChange={set("price")} /></Field>
        <Field label={t("supplierDash.currency")} hint={f.currency !== "UZS" ? t("supplierDash.currencyHint") : undefined}>
          <Select value={f.currency} onChange={set("currency")}>{["UZS", "USD", "EUR", "RUB", "CNY", "KZT"].map((c) => <option key={c}>{c}</option>)}</Select>
        </Field>
        <Field label={t("common.unit") + " *"} hint={unitHint}><UnitSelect value={f.unit_id} onChange={(v) => setF({ ...f, unit_id: v })} /></Field>
        {!offer && <Field label={t("common.priceType")}>
          <Select value={f.price_type} onChange={set("price_type")}>{["wholesale", "retail", "negotiated", "other"].map((p) => <option key={p} value={p}>{t(`priceType.${p}`)}</option>)}</Select>
        </Field>}
        <Field label="MOQ" hint={t("supplierDash.inOfferUnits")} htmlFor="o-moq"><Input id="o-moq" type="number" min={0} value={f.moq} onChange={set("moq")} /></Field>
        <Field label={t("compare.stock")} hint={t("supplierDash.inOfferUnits")} htmlFor="o-qty"><Input id="o-qty" type="number" min={0} value={f.available_qty} onChange={set("available_qty")} /></Field>
        {!offer && <Field label={t("supplierDash.warehouseRegion") + " *"}><RegionSelect value={f.region_id} onChange={(v) => setF({ ...f, region_id: v })} allLabel={t("common.select")} /></Field>}
        <Field label={t("supplierDash.validUntil")} htmlFor="o-valid"><Input id="o-valid" type="date" value={f.valid_until} onChange={set("valid_until")} /></Field>
        <div className="flex items-end pb-2"><Switch checked={f.delivery_available} onChange={(v) => setF({ ...f, delivery_available: v })} label={t("supplierDash.delivery")} /></div>
        {f.delivery_available && <Field label={t("supplierDash.deliveryCost")} hint={t("supplierDash.deliveryCostHint")} htmlFor="o-dc"><Input id="o-dc" type="number" min={0} value={f.delivery_cost_uzs} onChange={set("delivery_cost_uzs")} /></Field>}
        {!offer && <div className="md:col-span-2"><Field label={t("supplierDash.sourceUrl")} htmlFor="o-url"><Input id="o-url" type="url" value={f.source_url} onChange={set("source_url")} placeholder="https://" /></Field></div>}
      </div>
      <Alert tone="blue" className="mt-3">{t("supplierDash.historyNote")}</Alert>
      {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
      <ProductFormDialog open={newProduct} onClose={() => setNewProduct(false)} onSaved={(p) => setProduct(p)} />
    </Dialog>
  );
}

function QuotesTab() {
  const { t, lang } = useI18n();
  const { data: units } = useUnits();
  const q = useQuery({ queryKey: ["quotes-received"], queryFn: () => api.get<Quote[]>("/quotes/received") });
  const [answering, setAnswering] = useState<Quote | null>(null);
  return (
    <Card>
      <CardHeader title={t("supplierDash.quotes")} />
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState /> : (
        <Table>
          <thead><tr><Th>{t("common.product")}</Th><Th>{t("common.quantity")}</Th><Th>{t("quote.message")}</Th><Th>{t("common.status")}</Th><Th>{t("procurement.created")}</Th><Th /></tr></thead>
          <tbody>{q.data.map((x) => (
            <tr key={x.id}>
              <Td className="font-medium">{x.product.name}<p className="text-xs text-muted-foreground">{x.supplier.name}</p></Td>
              <Td>{fmtNum(x.quantity, lang)} {units?.find((u) => u.id === x.unit_id)?.symbol}</Td>
              <Td className="max-w-xs text-xs">{x.message ?? "—"}</Td>
              <Td><QuoteStatus s={x.status} /></Td>
              <Td className="text-xs">{fmtDate(x.created_at, lang)}</Td>
              <Td>{x.status === "open" && <Button size="sm" onClick={() => setAnswering(x)}>{t("supplierDash.respond")}</Button>}</Td>
            </tr>))}</tbody>
        </Table>
      )}
      {answering && <RespondDialog quote={answering} onClose={() => setAnswering(null)} />}
    </Card>
  );
}

function RespondDialog({ quote, onClose }: { quote: Quote; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [price, setPrice] = useState("");
  const [unit, setUnit] = useState<number | "">(quote.unit_id);
  const [msg, setMsg] = useState("");
  const [valid, setValid] = useState("");
  const m = useMutation({
    mutationFn: () => api.post(`/quotes/${quote.id}/responses`, { price, unit_id: unit, message: msg || null, valid_until: valid ? `${valid}T23:59:59+05:00` : null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["quotes-received"] }); onClose(); },
  });
  return (
    <Dialog open onClose={onClose} title={t("supplierDash.respondTitle", { p: quote.product.name })}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button><Button onClick={() => m.mutate()} loading={m.isPending} disabled={!price || !unit}>{t("common.submit")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t("supplierDash.price") + " (UZS)"} htmlFor="r-price"><Input id="r-price" type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)} /></Field>
        <Field label={t("common.unit")}><UnitSelect value={unit} onChange={setUnit} /></Field>
        <Field label={t("supplierDash.validUntil")} htmlFor="r-valid"><Input id="r-valid" type="date" value={valid} onChange={(e) => setValid(e.target.value)} /></Field>
        <div className="md:col-span-2"><Field label={t("quote.message")} htmlFor="r-msg"><Textarea id="r-msg" value={msg} onChange={(e) => setMsg(e.target.value)} maxLength={2000} /></Field></div>
      </div>
      {m.error && <Alert tone="red" className="mt-3">{(m.error as Error).message}</Alert>}
    </Dialog>
  );
}

function ProfileTab({ supplier }: { supplier: SupplierDetail }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [evidence, setEvidence] = useState("");
  const req = useMutation({ mutationFn: () => api.post(`/suppliers/${supplier.id}/verification-request`, undefined, { evidence: evidence || undefined }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-suppliers"] }) });
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader title={supplier.name} action={can("suppliers.manage_own") && <Button size="sm" variant="outline" onClick={() => setOpen(true)}><Pencil className="h-3.5 w-3.5" />{t("common.edit")}</Button>} />
        <CardBody className="space-y-1 text-sm">
          <p>{t(`supplierType.${supplier.supplier_type}`)}</p>
          <p className="text-muted-foreground">{supplier.description ?? "—"}</p>
          <p>{supplier.phone} {supplier.email}</p>
          <Link to={`/suppliers/${supplier.id}`} className="text-xs text-primary">{t("supplierDash.publicProfile")}</Link>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title={t("supplierDash.verification")} description={t("supplierDash.verificationHint")} />
        <CardBody className="space-y-3">
          <VerificationBadge status={supplier.verification_status} />
          {supplier.verification_status === "unverified" || supplier.verification_status === "rejected" ? (
            <>
              <Field label={t("supplierDash.evidence")} hint={t("supplierDash.evidenceHint")}><Textarea value={evidence} onChange={(e) => setEvidence(e.target.value)} maxLength={5000} /></Field>
              <Button onClick={() => req.mutate()} loading={req.isPending}><ShieldCheck className="h-4 w-4" />{t("supplierDash.requestVerification")}</Button>
              {req.error && <Alert tone="red">{(req.error as Error).message}</Alert>}
            </>
          ) : supplier.verification_status === "pending" ? <Alert tone="amber">{t("supplierDash.pending")}</Alert> : <Alert tone="green">{t("supplierDash.verified")}</Alert>}
        </CardBody>
      </Card>
      {open && <ProfileDialog supplier={supplier} onClose={() => setOpen(false)} />}
    </div>
  );
}

function ProfileDialog({ supplier, onClose }: { supplier?: SupplierDetail; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [f, setF] = useState({ name: supplier?.name ?? "", legal_name: supplier?.legal_name ?? "", tin: supplier?.tin ?? "",
    supplier_type: supplier?.supplier_type ?? "wholesaler", description: supplier?.description ?? "", phone: supplier?.phone ?? "",
    email: supplier?.email ?? "", website: supplier?.website ?? "", address: supplier?.address ?? "" });
  const [region, setRegion] = useState<number | "">(supplier?.region?.id ?? "");
  const [cats, setCats] = useState<number[]>(supplier?.categories.map((c) => c.id) ?? []);
  const [addCat, setAddCat] = useState<number | "">("");
  const n = (v: string) => (v.trim() === "" ? null : v.trim());
  const save = useMutation({
    mutationFn: () => {
      const body = { name: f.name, legal_name: n(f.legal_name), tin: n(f.tin), supplier_type: f.supplier_type, description: n(f.description),
        phone: n(f.phone), email: n(f.email), website: n(f.website), address: n(f.address), region_id: region, category_ids: cats,
        locations: supplier?.locations.map((l) => ({ kind: l.kind, name: l.name, region_id: l.region.id, address: l.address, lat: l.lat, lng: l.lng }))
          ?? (region ? [{ kind: "warehouse", region_id: region }] : []) };
      return supplier ? api.put(`/suppliers/${supplier.id}`, body) : api.post("/suppliers", body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-suppliers"] }); onClose(); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const { nm } = useI18n();
  const { data: allCats } = useQuery({ queryKey: ["categories", false], queryFn: () => api.get<{ id: number; name_uz: string; name_ru: string; name_en: string | null }[]>("/categories") });
  return (
    <Dialog open onClose={onClose} wide title={supplier ? t("supplierDash.editProfile") : t("supplierDash.createProfile")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button><Button onClick={() => save.mutate()} loading={save.isPending} disabled={!f.name || !region}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t("common.name") + " *"}><Input value={f.name} onChange={set("name")} /></Field>
        <Field label={t("supplier.legalName")}><Input value={f.legal_name} onChange={set("legal_name")} /></Field>
        <Field label={t("auth.tin")}><Input value={f.tin} onChange={set("tin")} inputMode="numeric" /></Field>
        <Field label={t("supplier.type")}><Select value={f.supplier_type} onChange={set("supplier_type")}>
          {["manufacturer", "wholesaler", "distributor", "importer", "retail", "other"].map((s) => <option key={s} value={s}>{t(`supplierType.${s}`)}</option>)}</Select></Field>
        <Field label={t("common.region") + " *"}><RegionSelect value={region} onChange={setRegion} allLabel={t("common.select")} /></Field>
        <Field label={t("auth.phone")}><Input value={f.phone} onChange={set("phone")} /></Field>
        <Field label={t("auth.email")}><Input type="email" value={f.email} onChange={set("email")} /></Field>
        <Field label={t("supplier.website")}><Input type="url" value={f.website} onChange={set("website")} placeholder="https://" /></Field>
        <div className="md:col-span-2"><Field label={t("supplier.address")}><Input value={f.address} onChange={set("address")} /></Field></div>
        <div className="md:col-span-2"><Field label={t("common.description")}><Textarea value={f.description} onChange={set("description")} /></Field></div>
        <div className="md:col-span-2">
          <Field label={t("supplier.categories")}>
            <div className="flex flex-wrap items-center gap-2">
              {cats.map((id) => <button key={id} type="button" onClick={() => setCats(cats.filter((c) => c !== id))} className="rounded-full bg-muted px-2 py-0.5 text-xs">
                {nm(allCats?.find((c) => c.id === id))} ×</button>)}
              <div className="w-56"><CategorySelect value={addCat} allLabel={t("supplier.addCategory")} onChange={(v) => { if (v && !cats.includes(v)) setCats([...cats, v]); setAddCat(""); }} /></div>
            </div>
          </Field>
        </div>
      </div>
      {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
    </Dialog>
  );
}
