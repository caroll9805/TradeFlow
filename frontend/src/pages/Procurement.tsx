import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useUnits } from "@/lib/hooks";
import type { Quote } from "@/lib/types";
import { fmtDate, fmtNum } from "@/lib/format";
import { Badge, Button, Card, CardHeader, ConfirmDialog, EmptyState, ErrorState, LoadingState, PageHeader, Table, Td, Th } from "@/components/ui";

export function QuoteStatus({ s }: { s: string }) {
  const { t } = useI18n();
  return <Badge tone={s === "answered" ? "green" : s === "open" ? "blue" : "slate"}>{t(`quote.status.${s}`)}</Badge>;
}

export default function Procurement() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const { data: units } = useUnits();
  const unitSym = (id: number) => units?.find((u) => u.id === id)?.symbol ?? "";
  const q = useQuery({ queryKey: ["quotes-sent"], queryFn: () => api.get<Quote[]>("/quotes/sent") });
  const [closing, setClosing] = useState<Quote | null>(null);
  const close = useMutation({ mutationFn: (id: number) => api.post(`/quotes/${id}/close`), onSuccess: () => { setClosing(null); qc.invalidateQueries({ queryKey: ["quotes-sent"] }); } });

  return (
    <div className="space-y-5">
      <PageHeader title={t("procurement.title")} description={t("procurement.subtitle")}
        actions={<Link to="/catalog"><Button>{t("procurement.findProducts")}</Button></Link>} />
      <Card>
        <CardHeader title={t("procurement.quotes")} description={t("procurement.quotesHint")} />
        {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState description={t("procurement.empty")} /> : (
          <Table>
            <thead><tr><Th>{t("common.product")}</Th><Th>{t("common.supplier")}</Th><Th>{t("common.quantity")}</Th><Th>{t("common.status")}</Th>
              <Th>{t("procurement.responses")}</Th><Th>{t("procurement.created")}</Th><Th /></tr></thead>
            <tbody>{q.data.map((x) => (
              <tr key={x.id}>
                <Td><Link to={`/products/${x.product.id}`} className="font-medium hover:text-primary">{x.product.name}</Link>{x.message && <p className="text-xs text-muted-foreground">{x.message}</p>}</Td>
                <Td><Link to={`/suppliers/${x.supplier.id}`} className="hover:text-primary">{x.supplier.name}</Link></Td>
                <Td>{fmtNum(x.quantity, lang)} {unitSym(x.unit_id)}</Td>
                <Td><QuoteStatus s={x.status} /></Td>
                <Td>{x.responses.length ? x.responses.map((r) => (
                  <div key={r.id} className="text-xs"><b>{fmtNum(r.price, lang)} {r.currency}/{unitSym(r.unit_id)}</b>
                    {r.valid_until && <span className="text-muted-foreground"> · {t("procurement.validUntil")} {fmtDate(r.valid_until, lang)}</span>}
                    {r.message && <p className="text-muted-foreground">{r.message}</p>}</div>)) : <span className="text-xs text-muted-foreground">—</span>}</Td>
                <Td className="text-xs">{fmtDate(x.created_at, lang)}</Td>
                <Td>{x.status !== "closed" && <Button size="sm" variant="outline" onClick={() => setClosing(x)}>{t("procurement.close")}</Button>}</Td>
              </tr>))}</tbody>
          </Table>
        )}
      </Card>
      <ConfirmDialog open={!!closing} title={t("procurement.closeTitle")} message={t("procurement.closeMsg", { p: closing?.product.name ?? "" })}
        onCancel={() => setClosing(null)} onConfirm={() => closing && close.mutate(closing.id)} loading={close.isPending} />
    </div>
  );
}
