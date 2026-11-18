import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkCheck, ExternalLink, Globe, Mail, MapPin, Phone, Star } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { SupplierDetail, SupplierLite } from "@/lib/types";
import { fmtDate, fmtNum, fmtUZS } from "@/lib/format";
import { Alert, Badge, Button, Card, CardBody, CardHeader, ConfirmDialog, EmptyState, ErrorState, Field, LoadingState, PageHeader, Select,
  Table, Td, Textarea, Th } from "@/components/ui";
import { PriceTypeBadge, ProvenanceBadge, SimulatedBadge, VerificationBadge } from "@/components/badges";

export default function SupplierProfile() {
  const { id } = useParams();
  const sid = Number(id);
  const { t, nm, lang } = useI18n();
  const { user, can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["supplier", sid], queryFn: () => api.get<SupplierDetail>(`/suppliers/${sid}`) });
  const saved = useQuery({ queryKey: ["saved-suppliers"], queryFn: () => api.get<{ supplier: SupplierLite }[]>("/saved/suppliers"), enabled: !!user });
  const isSaved = saved.data?.some((x) => x.supplier.id === sid);
  const toggle = useMutation({ mutationFn: () => (isSaved ? api.del(`/saved/suppliers/${sid}`) : api.put(`/saved/suppliers/${sid}`)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-suppliers"] }) });
  const [verifyTo, setVerifyTo] = useState<string | null>(null);
  const verify = useMutation({ mutationFn: (status: string) => api.post(`/suppliers/${sid}/verification`, { status }),
    onSuccess: () => { setVerifyTo(null); qc.invalidateQueries({ queryKey: ["supplier", sid] }); } });

  if (q.isLoading) return <LoadingState />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const s = q.data;

  return (
    <div className="space-y-5">
      <PageHeader title={s.name} description={`${t(`supplierType.${s.supplier_type}`)} · ${s.region ? nm(s.region) : ""}`}
        actions={<>
          {s.is_simulated && <SimulatedBadge />}
          <VerificationBadge status={s.verification_status} />
          {user && <Button variant="outline" onClick={() => toggle.mutate()} loading={toggle.isPending}>
            {isSaved ? <BookmarkCheck className="h-4 w-4 text-primary" /> : <Bookmark className="h-4 w-4" />}{isSaved ? t("common.saved") : t("common.save")}</Button>}
          {can("suppliers.verify") && (s.verification_status !== "verified"
            ? <Button onClick={() => setVerifyTo("verified")}>{t("supplier.verify")}</Button>
            : <Button variant="outline" onClick={() => setVerifyTo("unverified")}>{t("supplier.unverify")}</Button>)}
        </>} />
      {s.verification_status !== "verified" && <Alert tone="blue">{t("supplier.notVerifiedNote")}</Alert>}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title={t("supplier.about")} />
          <CardBody className="space-y-2 text-sm">
            {s.description && <p className="text-muted-foreground">{s.description}</p>}
            {s.legal_name && <p><span className="text-muted-foreground">{t("supplier.legalName")}:</span> {s.legal_name}</p>}
            {s.tin && <p><span className="text-muted-foreground">{t("auth.tin")}:</span> {s.tin}</p>}
            {s.phone && <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-muted-foreground" />{s.phone}</p>}
            {s.email && <p className="flex items-center gap-2"><Mail className="h-4 w-4 text-muted-foreground" />{s.email}</p>}
            {s.website && <a href={s.website} target="_blank" rel="noopener noreferrer nofollow" className="flex items-center gap-2 text-primary"><Globe className="h-4 w-4" />{s.website}</a>}
            {Object.entries(s.social_links ?? {}).map(([k, v]) => <a key={k} href={v} target="_blank" rel="noopener noreferrer nofollow" className="flex items-center gap-2 text-primary"><ExternalLink className="h-4 w-4" />{k}</a>)}
            {s.address && <p className="flex items-center gap-2"><MapPin className="h-4 w-4 text-muted-foreground" />{s.address}</p>}
            {s.rating_avg !== null && <p className="flex items-center gap-1"><Star className="h-4 w-4 text-amber-500" />{fmtNum(s.rating_avg, lang, 1)} · {t("supplier.ratings", { n: s.rating_count })}</p>}
            <div className="flex flex-wrap gap-1 pt-1">{s.categories.map((c) => <Badge key={c.id} tone="slate">{nm(c)}</Badge>)}</div>
            <p className="pt-2 text-xs text-muted-foreground">{t("supplier.registered")}: {fmtDate(s.created_at, lang)}</p>
          </CardBody>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title={t("supplier.locations")} description={t("supplier.locationsHint")} />
          <CardBody>
            {s.locations.length ? (
              <ul className="space-y-2 text-sm">{s.locations.map((l) => (
                <li key={l.id} className="flex items-center gap-2"><MapPin className="h-4 w-4 text-primary" /><b>{t(`location.${l.kind}`)}</b>
                  {l.name && `· ${l.name}`} · {nm(l.region)} {l.address && `· ${l.address}`}</li>))}</ul>
            ) : <EmptyState />}
          </CardBody>
        </Card>
      </div>
      <Card>
        <CardHeader title={t("supplier.offers")} description={t("catalog.offersN", { n: s.offers?.length ?? 0 })} />
        {!s.offers?.length ? <EmptyState /> : (
          <Table>
            <thead><tr><Th>{t("common.product")}</Th><Th className="text-right">{t("compare.offerPrice")}</Th><Th className="text-right">{t("common.pricePerUnit")}</Th>
              <Th>MOQ</Th><Th>{t("compare.stock")}</Th><Th>{t("common.region")}</Th><Th>{t("common.source")}</Th><Th>{t("common.updated")}</Th></tr></thead>
            <tbody>{s.offers.map((o) => (
              <tr key={o.id}>
                <Td><Link to={`/products/${o.product.id}`} className="font-medium hover:text-primary">{o.product.name}</Link><div className="mt-0.5"><PriceTypeBadge type={o.price_type} /></div></Td>
                <Td className="whitespace-nowrap text-right">{fmtNum(o.original_price, lang)} {o.original_currency}/{o.unit.symbol}</Td>
                <Td className="whitespace-nowrap text-right">{fmtUZS(o.price_per_base_unit_uzs, lang)}/{o.product.base_unit}</Td>
                <Td>{fmtNum(o.moq, lang)}</Td><Td>{o.available_qty === null ? "—" : fmtNum(o.available_qty, lang)}</Td>
                <Td>{nm(o.region)}</Td>
                <Td><div className="flex flex-wrap gap-1"><ProvenanceBadge kind={o.provenance_kind} />{o.is_simulated && <SimulatedBadge />}</div></Td>
                <Td className="text-xs">{fmtDate(o.price_updated_at, lang)}</Td>
              </tr>))}</tbody>
          </Table>
        )}
      </Card>
      {can("quotes.request") && s.organization_id && !user?.organizations.some((o) => o.id === s.organization_id) && <RateCard supplierId={sid} />}
      <ConfirmDialog open={!!verifyTo} title={t("supplier.verifyTitle")} message={t("supplier.verifyMessage", { s: s.name, st: t(`verification.${verifyTo ?? "verified"}`) })}
        onCancel={() => setVerifyTo(null)} onConfirm={() => verifyTo && verify.mutate(verifyTo)} loading={verify.isPending} />
    </div>
  );
}

function RateCard({ supplierId }: { supplierId: number }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [score, setScore] = useState("5");
  const [comment, setComment] = useState("");
  const m = useMutation({ mutationFn: () => api.post(`/suppliers/${supplierId}/ratings`, { score: Number(score), comment: comment || null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["supplier", supplierId] }) });
  return (
    <Card>
      <CardHeader title={t("supplier.rate")} description={t("supplier.rateHint")} />
      <CardBody className="grid gap-3 md:grid-cols-4">
        <Field label={t("supplier.score")}><Select value={score} onChange={(e) => setScore(e.target.value)}>{[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{"★".repeat(n)}</option>)}</Select></Field>
        <div className="md:col-span-2"><Field label={t("supplier.comment")}><Textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} className="min-h-[38px]" /></Field></div>
        <div className="flex items-end"><Button onClick={() => m.mutate()} loading={m.isPending}>{t("common.submit")}</Button></div>
        {m.isSuccess && <Alert tone="green" className="md:col-span-4">{t("supplier.rated")}</Alert>}
        {m.error && <Alert tone="red" className="md:col-span-4">{(m.error as Error).message}</Alert>}
      </CardBody>
    </Card>
  );
}
