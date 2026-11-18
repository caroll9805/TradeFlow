import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCategory } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { CategoryAttribute, Product } from "@/lib/types";
import { Alert, Button, Dialog, Field, Input, Select, Textarea } from "@/components/ui";
import { CategorySelect, UnitSelect } from "@/components/selects";

type Vals = Record<number, unknown>;

export function AttributeInput({ a, value, onChange }: { a: CategoryAttribute; value: unknown; onChange: (v: unknown) => void }) {
  const { t, lbl } = useI18n();
  const id = `attr-${a.id}`;
  switch (a.data_type) {
    case "number":
      return <Input id={id} type="number" step="any" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} />;
    case "boolean":
      return <Select id={id} value={value === true ? "1" : value === false ? "0" : ""} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "1")}>
        <option value="">—</option><option value="1">{t("common.yes")}</option><option value="0">{t("common.no")}</option></Select>;
    case "date":
      return <Input id={id} type="date" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || null)} />;
    case "select":
      return <Select id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">—</option>{a.options.map((o) => <option key={o.id} value={o.value}>{lbl(o)}</option>)}</Select>;
    case "multiselect": {
      const arr = Array.isArray(value) ? (value as string[]) : [];
      return <div className="flex flex-wrap gap-2">{a.options.map((o) => (
        <label key={o.id} className="flex items-center gap-1 text-xs">
          <input type="checkbox" checked={arr.includes(o.value)}
            onChange={(e) => onChange(e.target.checked ? [...arr, o.value] : arr.filter((x) => x !== o.value))} />{lbl(o)}
        </label>))}</div>;
    }
    default:
      return <Input id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

/** Create/edit a product. Attribute fields are generated from the category definition in the DB. */
export function ProductFormDialog({ open, onClose, product, onSaved }: { open: boolean; onClose: () => void; product?: Product | null; onSaved?: (p: Product) => void }) {
  const { t, nm } = useI18n();
  const qc = useQueryClient();
  const [categoryId, setCategoryId] = useState<number | "">(product?.category_id ?? "");
  const [form, setForm] = useState({ name: "", description: "", brand: "", model: "", sku: "", barcode: "", origin_type: "unknown", country_of_origin: "", search_terms: "" });
  const [unitId, setUnitId] = useState<number | "">(product?.base_unit.id ?? "");
  const [attrs, setAttrs] = useState<Vals>({});
  const { data: cat } = useCategory(categoryId || null);

  useEffect(() => {
    if (!open) return;
    setCategoryId(product?.category_id ?? "");
    setUnitId(product?.base_unit.id ?? "");
    setForm({ name: product?.name ?? "", description: product?.description ?? "", brand: product?.brand ?? "", model: product?.model ?? "",
      sku: product?.sku ?? "", barcode: product?.barcode ?? "", origin_type: product?.origin_type ?? "unknown",
      country_of_origin: product?.country_of_origin ?? "", search_terms: product?.search_terms.join(", ") ?? "" });
    setAttrs(Object.fromEntries((product?.attributes ?? []).map((a) => [a.attribute_id, a.value])));
  }, [open, product]);

  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...form, description: form.description || null, brand: form.brand || null, model: form.model || null, sku: form.sku || null,
        barcode: form.barcode || null, country_of_origin: form.country_of_origin || null, category_id: categoryId, base_unit_id: unitId,
        search_terms: form.search_terms.split(",").map((s) => s.trim()).filter(Boolean),
        attributes: (cat?.attributes ?? []).filter((a) => attrs[a.id] !== undefined).map((a) => ({ attribute_id: a.id, value: attrs[a.id] })),
      };
      return product ? api.put<Product>(`/products/${product.id}`, body) : api.post<Product>("/products", body);
    },
    onSuccess: (p) => { qc.invalidateQueries({ queryKey: ["products"] }); qc.invalidateQueries({ queryKey: ["product", p.id] }); onSaved?.(p); onClose(); },
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  return (
    <Dialog open={open} onClose={onClose} wide title={product ? t("product.edit") : t("product.add")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
        <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!form.name || !categoryId || !unitId}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t("common.name") + " *"} htmlFor="pname"><Input id="pname" value={form.name} onChange={set("name")} /></Field>
        <Field label={t("common.category") + " *"}><CategorySelect value={categoryId} onChange={(v) => { setCategoryId(v); setAttrs({}); }} allLabel={t("common.select")} /></Field>
        <Field label={t("product.baseUnit") + " *"} hint={t("product.baseUnitHint")}><UnitSelect value={unitId} onChange={setUnitId} /></Field>
        <Field label={t("product.brand")} htmlFor="pbrand"><Input id="pbrand" value={form.brand} onChange={set("brand")} /></Field>
        <Field label={t("product.model")} htmlFor="pmodel"><Input id="pmodel" value={form.model} onChange={set("model")} /></Field>
        <Field label="SKU" htmlFor="psku"><Input id="psku" value={form.sku} onChange={set("sku")} /></Field>
        <Field label={t("product.barcode")} htmlFor="pbar"><Input id="pbar" inputMode="numeric" value={form.barcode} onChange={set("barcode")} /></Field>
        <Field label={t("product.origin")}>
          <Select value={form.origin_type} onChange={set("origin_type")}>
            {["domestic", "import", "unknown"].map((o) => <option key={o} value={o}>{t(`origin.${o}`)}</option>)}
          </Select>
        </Field>
        <Field label={t("product.country")} hint="ISO, e.g. UZ" htmlFor="pcountry"><Input id="pcountry" maxLength={2} value={form.country_of_origin} onChange={(e) => setForm({ ...form, country_of_origin: e.target.value.toUpperCase() })} /></Field>
        <Field label={t("product.searchTerms")} hint={t("product.searchTermsHint")} htmlFor="pterms"><Input id="pterms" value={form.search_terms} onChange={set("search_terms")} /></Field>
        <div className="md:col-span-2"><Field label={t("common.description")} htmlFor="pdesc"><Textarea id="pdesc" value={form.description} onChange={set("description")} /></Field></div>
      </div>
      {cat?.attributes && cat.attributes.length > 0 && (
        <div className="mt-4 border-t border-border pt-4">
          <p className="mb-2 text-xs font-semibold text-muted-foreground">{t("product.attributesFor", { c: nm(cat) })}</p>
          <div className="grid gap-3 md:grid-cols-2">
            {cat.attributes.map((a) => (
              <Field key={a.id} label={nm(a) + (a.is_required ? " *" : "")} htmlFor={`attr-${a.id}`}>
                <AttributeInput a={a} value={attrs[a.id]} onChange={(v) => setAttrs({ ...attrs, [a.id]: v })} />
              </Field>
            ))}
          </div>
        </div>
      )}
      {cat?.requires_compliance_note && <Alert className="mt-3">{cat.compliance_note}</Alert>}
      {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
    </Dialog>
  );
}
