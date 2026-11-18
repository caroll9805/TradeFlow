import { Select } from "@/components/ui";
import { useCategories, useRegions, useUnits } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";

type V = number | "" | null | undefined;

export function RegionSelect({ value, onChange, allLabel, id, required }: { value: V; onChange: (v: number | "") => void; allLabel?: string; id?: string; required?: boolean }) {
  const { data } = useRegions();
  const { t, nm } = useI18n();
  return (
    <Select id={id} required={required} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : "")} aria-label={t("common.region")}>
      <option value="">{allLabel ?? t("common.allRegions")}</option>
      {data?.map((r) => <option key={r.id} value={r.id}>{nm(r)}</option>)}
    </Select>
  );
}

export function CategorySelect({ value, onChange, allLabel, id, required }: { value: V; onChange: (v: number | "") => void; allLabel?: string; id?: string; required?: boolean }) {
  const { data } = useCategories();
  const { t, nm } = useI18n();
  return (
    <Select id={id} required={required} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : "")} aria-label={t("common.category")}>
      <option value="">{allLabel ?? t("common.allCategories")}</option>
      {data?.map((c) => <option key={c.id} value={c.id}>{nm(c)}</option>)}
    </Select>
  );
}

export function UnitSelect({ value, onChange, id, filter }: { value: V; onChange: (v: number | "") => void; id?: string; filter?: (code: string) => boolean }) {
  const { data } = useUnits();
  const { t, nm } = useI18n();
  return (
    <Select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : "")} aria-label={t("common.unit")}>
      <option value="">{t("common.select")}</option>
      {data?.filter((u) => !filter || filter(u.code)).map((u) => <option key={u.id} value={u.id}>{nm(u)} ({u.symbol})</option>)}
    </Select>
  );
}

export function PriceTypeSelect({ value, onChange, id }: { value: string; onChange: (v: string) => void; id?: string }) {
  const { t } = useI18n();
  return (
    <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-label={t("common.priceType")}>
      <option value="">{t("common.allPriceTypes")}</option>
      {["wholesale", "retail", "negotiated", "other"].map((p) => <option key={p} value={p}>{t(`priceType.${p}`)}</option>)}
    </Select>
  );
}
