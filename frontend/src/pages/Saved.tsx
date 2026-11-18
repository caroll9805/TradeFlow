import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Product, SupplierLite } from "@/lib/types";
import { fmtDate } from "@/lib/format";
import { Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, Table, Td, Th } from "@/components/ui";
import { SimulatedBadge, VerificationBadge } from "@/components/badges";

export default function Saved() {
  const { t, nm, lang } = useI18n();
  const qc = useQueryClient();
  const products = useQuery({ queryKey: ["saved-products"], queryFn: () => api.get<{ id: number; created_at: string; product: Product }[]>("/saved/products") });
  const suppliers = useQuery({ queryKey: ["saved-suppliers"], queryFn: () => api.get<{ id: number; created_at: string; supplier: SupplierLite }[]>("/saved/suppliers") });
  const rmP = useMutation({ mutationFn: (id: number) => api.del(`/saved/products/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-products"] }) });
  const rmS = useMutation({ mutationFn: (id: number) => api.del(`/saved/suppliers/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-suppliers"] }) });

  return (
    <div className="space-y-5">
      <PageHeader title={t("saved.title")} description={t("saved.subtitle")} />
      <Card>
        <CardHeader title={t("saved.products")} />
        {products.isLoading ? <LoadingState /> : products.error ? <ErrorState error={products.error} /> : !products.data?.length ? <EmptyState description={t("saved.emptyProducts")} /> : (
          <Table><thead><tr><Th>{t("common.product")}</Th><Th>{t("common.category")}</Th><Th>{t("saved.savedAt")}</Th><Th /></tr></thead>
            <tbody>{products.data.map((s) => (
              <tr key={s.id}><Td><Link to={`/products/${s.product.id}`} className="font-medium hover:text-primary">{s.product.name}</Link> {s.product.is_simulated && <SimulatedBadge />}</Td>
                <Td>{s.product.category && nm(s.product.category)}</Td><Td className="text-xs">{fmtDate(s.created_at, lang)}</Td>
                <Td className="text-right"><Button size="icon" variant="ghost" aria-label={t("common.remove")} onClick={() => rmP.mutate(s.product.id)}><Trash2 className="h-4 w-4" /></Button></Td></tr>))}</tbody></Table>
        )}
      </Card>
      <Card>
        <CardHeader title={t("saved.suppliers")} />
        {suppliers.isLoading ? <LoadingState /> : suppliers.error ? <ErrorState error={suppliers.error} /> : !suppliers.data?.length ? <EmptyState description={t("saved.emptySuppliers")} /> : (
          <Table><thead><tr><Th>{t("common.supplier")}</Th><Th>{t("common.region")}</Th><Th>{t("compare.verification")}</Th><Th /></tr></thead>
            <tbody>{suppliers.data.map((s) => (
              <tr key={s.id}><Td><Link to={`/suppliers/${s.supplier.id}`} className="font-medium hover:text-primary">{s.supplier.name}</Link></Td>
                <Td>{s.supplier.region ? nm(s.supplier.region) : "—"}</Td><Td><VerificationBadge status={s.supplier.verification_status} /></Td>
                <Td className="text-right"><Button size="icon" variant="ghost" aria-label={t("common.remove")} onClick={() => rmS.mutate(s.supplier.id)}><Trash2 className="h-4 w-4" /></Button></Td></tr>))}</tbody></Table>
        )}
      </Card>
    </div>
  );
}
