import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Page, Product } from "@/lib/types";
import { Input } from "@/components/ui";

/** Debounce-free type-ahead backed by /products search. */
export function ProductPicker({ value, onChange, categoryId }: { value: Product | null; onChange: (p: Product | null) => void; categoryId?: number | "" }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const res = useQuery({
    queryKey: ["product-picker", q, categoryId],
    queryFn: () => api.get<Page<Product>>("/products", { q: q || undefined, category_id: categoryId || undefined, page_size: 8, has_offers: true }),
    enabled: open,
  });
  return (
    <div className="relative">
      <Input aria-label={t("picker.product")} placeholder={value ? value.name : t("picker.placeholder")} value={q}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)} onChange={(e) => { setQ(e.target.value); setOpen(true); }} />
      {open && (
        <ul className="absolute z-50 mt-1 max-h-72 w-full overflow-auto rounded-md border border-border bg-white shadow-lg" role="listbox">
          {res.data?.items.length ? res.data.items.map((p) => (
            <li key={p.id} role="option" aria-selected={value?.id === p.id}>
              <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-muted" onMouseDown={() => { onChange(p); setQ(""); setOpen(false); }}>
                {p.name}<span className="ml-2 text-xs text-muted-foreground">{p.offer_stats?.offers ?? 0}</span>
              </button>
            </li>
          )) : <li className="px-3 py-2 text-xs text-muted-foreground">{res.isLoading ? t("common.loading") : t("catalog.noResults")}</li>}
        </ul>
      )}
    </div>
  );
}
