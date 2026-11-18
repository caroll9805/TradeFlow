import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCategories, useCategory, useRegions, useUnits } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { Category, CategoryAttribute, Page, Region, Unit, User } from "@/lib/types";
import { fmtDate, fmtNum } from "@/lib/format";
import { Alert, Badge, Button, Card, CardBody, CardHeader, ConfirmDialog, Dialog, EmptyState, ErrorState, Field, Input, LoadingState,
  PageHeader, Pagination, Select, Switch, Table, Tabs, Td, Textarea, Th } from "@/components/ui";

type Tab = "categories" | "units" | "regions" | "users" | "roles" | "settings" | "rates" | "audit" | "demo" | "plans";

export default function PlatformAdmin() {
  const { t } = useI18n();
  const { can } = useAuth();
  const tabs: { value: Tab; perm: string }[] = [
    { value: "categories", perm: "catalog.manage" }, { value: "units", perm: "catalog.manage" }, { value: "regions", perm: "catalog.manage" },
    { value: "users", perm: "users.manage" }, { value: "roles", perm: "users.manage" }, { value: "settings", perm: "settings.manage" },
    { value: "rates", perm: "settings.manage" }, { value: "audit", perm: "audit.view" }, { value: "demo", perm: "demo.manage" }, { value: "plans", perm: "settings.manage" }];
  const allowed = tabs.filter((x) => can(x.perm));
  const [picked, setTab] = useState<Tab | null>(null);
  if (!allowed.length) return <div className="py-16 text-center text-sm text-muted-foreground">{t("common.forbidden")}</div>;
  const tab: Tab = picked && allowed.some((x) => x.value === picked) ? picked : allowed[0].value;
  return (
    <div className="space-y-5">
      <PageHeader title={t("admin.title")} description={t("admin.subtitle")} />
      <Tabs value={tab} onChange={setTab} items={allowed.map((x) => ({ value: x.value, label: t(`admin.tab.${x.value}`) }))} />
      {tab === "categories" && <CategoriesTab />}
      {tab === "units" && <UnitsTab />}
      {tab === "regions" && <RegionsTab />}
      {tab === "users" && <UsersTab />}
      {tab === "roles" && <RolesTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "rates" && <RatesTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "demo" && <DemoTab />}
      {tab === "plans" && <PlansTab />}
    </div>
  );
}

function CategoriesTab() {
  const { t, nm } = useI18n();
  const cats = useQuery({ queryKey: ["admin-categories"], queryFn: () => api.get<Category[]>("/categories", { include_inactive: true }) });
  const [sel, setSel] = useState<number | null>(null);
  const [edit, setEdit] = useState<Category | null | "new">(null);
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Card>
        <CardHeader title={t("admin.tab.categories")} action={<Button size="sm" onClick={() => setEdit("new")}><Plus className="h-4 w-4" />{t("common.add")}</Button>} />
        {cats.isLoading ? <LoadingState /> : cats.error ? <ErrorState error={cats.error} /> : (
          <ul className="divide-y divide-border">{cats.data?.map((c) => (
            <li key={c.id} className={`flex items-center justify-between px-5 py-2 text-sm ${sel === c.id ? "bg-primary/5" : ""}`}>
              <button className="text-left" onClick={() => setSel(c.id)}>{nm(c)} <span className="text-xs text-muted-foreground">({c.slug})</span>
                {!c.is_active && <Badge tone="slate" className="ml-1">{t("supplierDash.inactive")}</Badge>}</button>
              <Button size="sm" variant="ghost" onClick={() => setEdit(c)} aria-label={t("common.edit")}><Pencil className="h-3.5 w-3.5" /></Button>
            </li>))}</ul>
        )}
      </Card>
      <div className="lg:col-span-2">{sel ? <AttributesPanel categoryId={sel} /> : <Card><EmptyState title={t("admin.pickCategory")} /></Card>}</div>
      {edit && <CategoryDialog category={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
    </div>
  );
}

function CategoryDialog({ category, onClose }: { category: Category | null; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [f, setF] = useState({ slug: category?.slug ?? "", name_uz: category?.name_uz ?? "", name_ru: category?.name_ru ?? "", name_en: category?.name_en ?? "",
    description: category?.description ?? "", keywords: category?.keywords.join(", ") ?? "", freshness_hours: category?.freshness_hours ? String(category.freshness_hours) : "",
    is_active: category?.is_active ?? true, requires_compliance_note: category?.requires_compliance_note ?? false, compliance_note: category?.compliance_note ?? "",
    sort_order: String(category?.sort_order ?? 100), parent_id: category?.parent_id ?? ("" as number | "") });
  const { data: cats } = useCategories();
  const save = useMutation({
    mutationFn: () => {
      const body = { ...f, name_en: f.name_en || null, description: f.description || null, compliance_note: f.compliance_note || null,
        keywords: f.keywords.split(",").map((s) => s.trim()).filter(Boolean), freshness_hours: f.freshness_hours ? Number(f.freshness_hours) : null,
        sort_order: Number(f.sort_order), parent_id: f.parent_id || null };
      return category ? api.put(`/admin/categories/${category.id}`, body) : api.post("/admin/categories", body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-categories"] }); qc.invalidateQueries({ queryKey: ["categories"] }); onClose(); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const { nm } = useI18n();
  return (
    <Dialog open onClose={onClose} wide title={category ? t("admin.editCategory") : t("admin.newCategory")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button><Button onClick={() => save.mutate()} loading={save.isPending}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Slug" hint="a-z, 0-9, -"><Input value={f.slug} onChange={set("slug")} /></Field>
        <Field label={t("admin.parent")}><Select value={f.parent_id} onChange={(e) => setF({ ...f, parent_id: e.target.value ? Number(e.target.value) : "" })}>
          <option value="">—</option>{cats?.filter((c) => c.id !== category?.id).map((c) => <option key={c.id} value={c.id}>{nm(c)}</option>)}</Select></Field>
        <Field label={t("admin.nameUz")}><Input value={f.name_uz} onChange={set("name_uz")} /></Field>
        <Field label={t("admin.nameRu")}><Input value={f.name_ru} onChange={set("name_ru")} /></Field>
        <Field label={t("admin.nameEn")}><Input value={f.name_en} onChange={set("name_en")} /></Field>
        <Field label={t("admin.keywords")} hint={t("admin.keywordsHint")}><Input value={f.keywords} onChange={set("keywords")} /></Field>
        <Field label={t("admin.freshnessHours")} hint={t("admin.freshnessHint")}><Input type="number" min={1} value={f.freshness_hours} onChange={set("freshness_hours")} /></Field>
        <Field label={t("admin.sortOrder")}><Input type="number" value={f.sort_order} onChange={set("sort_order")} /></Field>
        <div className="md:col-span-2"><Field label={t("common.description")}><Textarea value={f.description} onChange={set("description")} /></Field></div>
        <Switch checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} label={t("supplierDash.active")} />
        <Switch checked={f.requires_compliance_note} onChange={(v) => setF({ ...f, requires_compliance_note: v })} label={t("admin.complianceNote")} />
        {f.requires_compliance_note && <div className="md:col-span-2"><Textarea value={f.compliance_note} onChange={set("compliance_note")} /></div>}
      </div>
      {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
    </Dialog>
  );
}

function AttributesPanel({ categoryId }: { categoryId: number }) {
  const { t, nm } = useI18n();
  const qc = useQueryClient();
  const { data: cat, isLoading } = useCategory(categoryId);
  const [edit, setEdit] = useState<CategoryAttribute | null | "new">(null);
  const [del, setDel] = useState<CategoryAttribute | null>(null);
  const rm = useMutation({ mutationFn: (id: number) => api.del(`/admin/attributes/${id}`),
    onSuccess: () => { setDel(null); qc.invalidateQueries({ queryKey: ["category", categoryId] }); } });
  if (isLoading || !cat) return <LoadingState />;
  return (
    <Card>
      <CardHeader title={t("admin.attributesOf", { c: nm(cat) })} description={t("admin.attributesHint")}
        action={<Button size="sm" onClick={() => setEdit("new")}><Plus className="h-4 w-4" />{t("admin.addAttribute")}</Button>} />
      {!cat.attributes?.length ? <EmptyState /> : (
        <Table>
          <thead><tr><Th>{t("md.code")}</Th><Th>{t("common.name")}</Th><Th>{t("admin.dataType")}</Th><Th>{t("admin.flags")}</Th><Th>{t("admin.options")}</Th><Th /></tr></thead>
          <tbody>{cat.attributes.map((a) => (
            <tr key={a.id}><Td className="font-mono text-xs">{a.code}</Td><Td>{nm(a)}</Td><Td className="text-xs">{a.data_type}</Td>
              <Td><div className="flex flex-wrap gap-1">{a.is_required && <Badge tone="red">{t("admin.required")}</Badge>}{a.is_filterable && <Badge tone="blue">{t("admin.filterable")}</Badge>}
                {a.is_matching_key && <Badge tone="violet">{t("admin.matchingKey")}</Badge>}</div></Td>
              <Td className="text-xs">{a.options.map((o) => o.value).join(", ") || "—"}</Td>
              <Td className="whitespace-nowrap"><Button size="sm" variant="ghost" onClick={() => setEdit(a)} aria-label={t("common.edit")}><Pencil className="h-3.5 w-3.5" /></Button>
                <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDel(a)} aria-label={t("common.remove")}><Trash2 className="h-3.5 w-3.5" /></Button></Td></tr>))}</tbody>
        </Table>
      )}
      {edit && <AttributeDialog categoryId={categoryId} attr={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
      <ConfirmDialog open={!!del} destructive title={t("admin.deleteAttribute")} message={t("admin.deleteAttributeMsg", { a: del?.code ?? "" })}
        onCancel={() => setDel(null)} onConfirm={() => del && rm.mutate(del.id)} loading={rm.isPending} />
    </Card>
  );
}

function AttributeDialog({ categoryId, attr, onClose }: { categoryId: number; attr: CategoryAttribute | null; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [f, setF] = useState({ code: attr?.code ?? "", name_uz: attr?.name_uz ?? "", name_ru: attr?.name_ru ?? "", name_en: attr?.name_en ?? "",
    data_type: attr?.data_type ?? "text", is_required: attr?.is_required ?? false, is_filterable: attr?.is_filterable ?? false,
    is_matching_key: attr?.is_matching_key ?? false, sort_order: String(attr?.sort_order ?? 0),
    options: attr?.options.map((o) => `${o.value}|${o.label_uz}|${o.label_ru}`).join("\n") ?? "" });
  const save = useMutation({
    mutationFn: () => {
      const options = f.options.split("\n").map((l) => l.trim()).filter(Boolean).map((l, i) => {
        const [value, uz, ru] = l.split("|").map((s) => s.trim());
        return { value, label_uz: uz || value, label_ru: ru || uz || value, sort_order: i };
      });
      const body = { code: f.code, name_uz: f.name_uz, name_ru: f.name_ru, name_en: f.name_en || null, data_type: f.data_type, is_required: f.is_required,
        is_filterable: f.is_filterable, is_matching_key: f.is_matching_key, sort_order: Number(f.sort_order), options };
      return attr ? api.put(`/admin/attributes/${attr.id}`, body) : api.post(`/admin/categories/${categoryId}/attributes`, body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["category", categoryId] }); onClose(); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialog open onClose={onClose} wide title={attr ? t("admin.editAttribute") : t("admin.addAttribute")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button><Button onClick={() => save.mutate()} loading={save.isPending}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t("md.code")} hint="a-z, 0-9, _"><Input value={f.code} onChange={set("code")} /></Field>
        <Field label={t("admin.dataType")}><Select value={f.data_type} onChange={set("data_type")}>
          {["text", "number", "boolean", "date", "select", "multiselect"].map((d) => <option key={d} value={d}>{d}</option>)}</Select></Field>
        <Field label={t("admin.nameUz")}><Input value={f.name_uz} onChange={set("name_uz")} /></Field>
        <Field label={t("admin.nameRu")}><Input value={f.name_ru} onChange={set("name_ru")} /></Field>
        <Field label={t("admin.nameEn")}><Input value={f.name_en} onChange={set("name_en")} /></Field>
        <Field label={t("admin.sortOrder")}><Input type="number" value={f.sort_order} onChange={set("sort_order")} /></Field>
        <div className="flex flex-wrap gap-4 md:col-span-2">
          <Switch checked={f.is_required} onChange={(v) => setF({ ...f, is_required: v })} label={t("admin.required")} />
          <Switch checked={f.is_filterable} onChange={(v) => setF({ ...f, is_filterable: v })} label={t("admin.filterable")} />
          <Switch checked={f.is_matching_key} onChange={(v) => setF({ ...f, is_matching_key: v })} label={t("admin.matchingKey")} />
        </div>
        {(f.data_type === "select" || f.data_type === "multiselect") && (
          <div className="md:col-span-2"><Field label={t("admin.options")} hint={t("admin.optionsHint")}>
            <Textarea className="font-mono text-xs" value={f.options} onChange={set("options")} placeholder={"cotton|Paxta|Хлопок\nwool|Jun|Шерсть"} /></Field></div>
        )}
      </div>
      {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
    </Dialog>
  );
}

function UnitsTab() {
  const { t, nm } = useI18n();
  const qc = useQueryClient();
  const { data, isLoading } = useUnits();
  const [open, setOpen] = useState<Unit | null | "new">(null);
  const [f, setF] = useState({ code: "", name_uz: "", name_ru: "", name_en: "", symbol: "", dimension: "mass", factor_to_base: "", aliases: "" });
  const start = (u: Unit | null) => {
    setF(u ? { code: u.code, name_uz: u.name_uz, name_ru: u.name_ru, name_en: u.name_en, symbol: u.symbol, dimension: u.dimension,
      factor_to_base: u.factor_to_base === null ? "" : String(u.factor_to_base), aliases: u.aliases.join(", ") }
      : { code: "", name_uz: "", name_ru: "", name_en: "", symbol: "", dimension: "mass", factor_to_base: "", aliases: "" });
    setOpen(u ?? "new");
  };
  const save = useMutation({
    mutationFn: () => {
      const body = { ...f, factor_to_base: f.factor_to_base || null, aliases: f.aliases.split(",").map((s) => s.trim()).filter(Boolean) };
      return open && open !== "new" ? api.put(`/admin/units/${open.id}`, body) : api.post("/admin/units", body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["units"] }); setOpen(null); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Card>
      <CardHeader title={t("admin.tab.units")} description={t("admin.unitsHint")} action={<Button size="sm" onClick={() => start(null)}><Plus className="h-4 w-4" />{t("common.add")}</Button>} />
      {isLoading ? <LoadingState /> : (
        <Table><thead><tr><Th>{t("md.code")}</Th><Th>{t("common.name")}</Th><Th>{t("admin.dimension")}</Th><Th>{t("admin.factor")}</Th><Th>{t("admin.aliases")}</Th><Th /></tr></thead>
          <tbody>{data?.map((u) => (
            <tr key={u.id}><Td className="font-mono text-xs">{u.code}</Td><Td>{nm(u)} ({u.symbol})</Td><Td className="text-xs">{u.dimension}</Td>
              <Td className="text-xs">{u.factor_to_base ?? t("admin.productSpecific")}</Td><Td className="text-xs">{u.aliases.join(", ")}</Td>
              <Td><Button size="sm" variant="ghost" onClick={() => start(u)} aria-label={t("common.edit")}><Pencil className="h-3.5 w-3.5" /></Button></Td></tr>))}</tbody></Table>
      )}
      <Dialog open={!!open} onClose={() => setOpen(null)} title={open === "new" ? t("admin.newUnit") : t("admin.editUnit")}
        footer={<><Button variant="outline" onClick={() => setOpen(null)}>{t("common.cancel")}</Button><Button onClick={() => save.mutate()} loading={save.isPending}>{t("common.save")}</Button></>}>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label={t("md.code")}><Input value={f.code} onChange={set("code")} /></Field>
          <Field label={t("admin.symbol")}><Input value={f.symbol} onChange={set("symbol")} /></Field>
          <Field label={t("admin.nameUz")}><Input value={f.name_uz} onChange={set("name_uz")} /></Field>
          <Field label={t("admin.nameRu")}><Input value={f.name_ru} onChange={set("name_ru")} /></Field>
          <Field label={t("admin.nameEn")}><Input value={f.name_en} onChange={set("name_en")} /></Field>
          <Field label={t("admin.dimension")}><Select value={f.dimension} onChange={set("dimension")}>{["mass", "volume", "length", "area", "count", "package"].map((d) => <option key={d}>{d}</option>)}</Select></Field>
          <Field label={t("admin.factor")} hint={t("admin.factorHint")}><Input type="number" step="any" value={f.factor_to_base} onChange={set("factor_to_base")} disabled={f.dimension === "package"} /></Field>
          <Field label={t("admin.aliases")}><Input value={f.aliases} onChange={set("aliases")} /></Field>
        </div>
        {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
      </Dialog>
    </Card>
  );
}

function RegionsTab() {
  const { t, nm } = useI18n();
  const qc = useQueryClient();
  const { data, isLoading } = useRegions();
  const [edit, setEdit] = useState<Region | null>(null);
  const [f, setF] = useState({ name_uz: "", name_ru: "", name_en: "", aliases: "", center_lat: "", center_lng: "" });
  const start = (r: Region) => { setEdit(r); setF({ name_uz: r.name_uz, name_ru: r.name_ru, name_en: r.name_en, aliases: r.aliases.join(", "),
    center_lat: r.center_lat === null ? "" : String(r.center_lat), center_lng: r.center_lng === null ? "" : String(r.center_lng) }); };
  const save = useMutation({
    mutationFn: () => api.put(`/admin/regions/${edit!.id}`, { code: edit!.code, sort_order: edit!.sort_order, ...f, aliases: f.aliases.split(",").map((s) => s.trim()).filter(Boolean),
      center_lat: f.center_lat || null, center_lng: f.center_lng || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["regions"] }); setEdit(null); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Card>
      <CardHeader title={t("admin.tab.regions")} description={t("admin.regionsHint")} />
      {isLoading ? <LoadingState /> : (
        <Table><thead><tr><Th>{t("md.code")}</Th><Th>{t("common.name")}</Th><Th>{t("admin.aliases")}</Th><Th>{t("admin.center")}</Th><Th /></tr></thead>
          <tbody>{data?.map((r) => (
            <tr key={r.id}><Td className="font-mono text-xs">{r.code}</Td><Td>{nm(r)}</Td><Td className="text-xs">{r.aliases.join(", ")}</Td>
              <Td className="text-xs">{r.center_lat}, {r.center_lng}</Td><Td><Button size="sm" variant="ghost" onClick={() => start(r)} aria-label={t("common.edit")}><Pencil className="h-3.5 w-3.5" /></Button></Td></tr>))}</tbody></Table>
      )}
      <Dialog open={!!edit} onClose={() => setEdit(null)} title={edit ? nm(edit) : ""}
        footer={<><Button variant="outline" onClick={() => setEdit(null)}>{t("common.cancel")}</Button><Button onClick={() => save.mutate()} loading={save.isPending}>{t("common.save")}</Button></>}>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label={t("admin.nameUz")}><Input value={f.name_uz} onChange={set("name_uz")} /></Field>
          <Field label={t("admin.nameRu")}><Input value={f.name_ru} onChange={set("name_ru")} /></Field>
          <Field label={t("admin.nameEn")}><Input value={f.name_en} onChange={set("name_en")} /></Field>
          <Field label={t("admin.aliases")}><Input value={f.aliases} onChange={set("aliases")} /></Field>
          <Field label="Lat"><Input type="number" step="any" value={f.center_lat} onChange={set("center_lat")} /></Field>
          <Field label="Lng"><Input type="number" step="any" value={f.center_lng} onChange={set("center_lng")} /></Field>
        </div>
        {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
      </Dialog>
    </Card>
  );
}

function UsersTab() {
  const { t, lang } = useI18n();
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const users = useQuery({ queryKey: ["admin-users", q, page], queryFn: () => api.get<Page<User>>("/admin/users", { q: q || undefined, page, page_size: 20 }) });
  const roles = useQuery({ queryKey: ["admin-roles"], queryFn: () => api.get<{ code: string; name_uz: string; name_ru: string }[]>("/admin/roles") });
  const upd = useMutation({ mutationFn: ({ id, body }: { id: number; body: object }) => api.patch(`/admin/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }) });
  return (
    <Card>
      <CardHeader title={t("admin.tab.users")} action={<Input className="w-64" placeholder={t("common.search")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label={t("common.search")} />} />
      {upd.error && <div className="px-5 pt-3"><Alert tone="red">{(upd.error as Error).message}</Alert></div>}
      {users.isLoading ? <LoadingState /> : users.error ? <ErrorState error={users.error} /> : !users.data?.items.length ? <EmptyState /> : (
        <div className="px-2">
          <Table><thead><tr><Th>{t("auth.email")}</Th><Th>{t("auth.fullName")}</Th><Th>{t("auth.organization")}</Th><Th>{t("admin.role")}</Th><Th>{t("admin.lastLogin")}</Th><Th>{t("common.status")}</Th></tr></thead>
            <tbody>{users.data.items.map((u) => (
              <tr key={u.id}><Td className="text-xs">{u.email}</Td><Td>{u.full_name}</Td><Td className="text-xs">{u.organizations.map((o) => o.name).join(", ")}</Td>
                <Td><Select className="h-8 text-xs" value={u.role} disabled={u.id === me?.id} onChange={(e) => upd.mutate({ id: u.id, body: { role_code: e.target.value } })} aria-label={t("admin.role")}>
                  {roles.data?.map((r) => <option key={r.code} value={r.code}>{lang === "ru" ? r.name_ru : r.name_uz}</option>)}</Select></Td>
                <Td className="text-xs">{fmtDate(u.last_login_at, lang, true)}</Td>
                <Td><Switch checked={u.is_active} onChange={(v) => upd.mutate({ id: u.id, body: { is_active: v } })} label={u.is_active ? t("supplierDash.active") : t("supplierDash.inactive")} /></Td></tr>))}</tbody></Table>
          <Pagination page={page} pageSize={20} total={users.data.total} onPage={setPage} />
        </div>
      )}
    </Card>
  );
}

function RolesTab() {
  const { t, lang } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const roles = useQuery({ queryKey: ["admin-roles"], queryFn: () => api.get<{ code: string; name_uz: string; name_ru: string; permissions: string[] }[]>("/admin/roles") });
  const perms = useQuery({ queryKey: ["admin-perms"], queryFn: () => api.get<{ code: string; description: string }[]>("/admin/permissions") });
  const save = useMutation({ mutationFn: ({ code, p }: { code: string; p: string[] }) => api.put(`/admin/roles/${code}/permissions`, { permission_codes: p }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-roles"] }) });
  if (roles.isLoading || perms.isLoading) return <LoadingState />;
  const editable = can("roles.manage");
  return (
    <Card>
      <CardHeader title={t("admin.tab.roles")} description={editable ? t("admin.rolesHint") : t("admin.rolesReadOnly")} />
      {save.error && <div className="px-5 pt-3"><Alert tone="red">{(save.error as Error).message}</Alert></div>}
      <Table>
        <thead><tr><Th>{t("admin.permission")}</Th>{roles.data?.map((r) => <Th key={r.code} className="text-center">{lang === "ru" ? r.name_ru : r.name_uz}</Th>)}</tr></thead>
        <tbody>{perms.data?.map((p) => (
          <tr key={p.code}><Td><p className="font-mono text-xs">{p.code}</p><p className="text-[11px] text-muted-foreground">{p.description}</p></Td>
            {roles.data?.map((r) => {
              const has = r.permissions.includes(p.code);
              return <Td key={r.code} className="text-center"><input type="checkbox" checked={has} disabled={!editable || save.isPending} aria-label={`${r.code} ${p.code}`}
                onChange={() => save.mutate({ code: r.code, p: has ? r.permissions.filter((x) => x !== p.code) : [...r.permissions, p.code] })} /></Td>;
            })}</tr>))}</tbody>
      </Table>
    </Card>
  );
}

function SettingsTab() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-settings"], queryFn: () => api.get<{ key: string; value: unknown; description: string | null; updated_at: string }[]>("/admin/settings") });
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const save = useMutation({ mutationFn: ({ key, value }: { key: string; value: unknown }) => api.put(`/admin/settings/${key}`, { value }),
    onSuccess: (_d, v) => { setDrafts((d) => { const n = { ...d }; delete n[v.key]; return n; }); qc.invalidateQueries({ queryKey: ["admin-settings"] }); } });
  const [err, setErr] = useState<string | null>(null);
  return (
    <Card>
      <CardHeader title={t("admin.tab.settings")} description={t("admin.settingsHint")} />
      {(err || save.error) && <div className="px-5 pt-3"><Alert tone="red">{err ?? (save.error as Error).message}</Alert></div>}
      {q.isLoading ? <LoadingState /> : (
        <CardBody className="space-y-4">
          {q.data?.map((s) => {
            const text = drafts[s.key] ?? JSON.stringify(s.value, null, typeof s.value === "object" ? 2 : 0);
            return (
              <div key={s.key} className="grid gap-2 border-b border-border pb-4 md:grid-cols-3">
                <div><p className="font-mono text-xs font-medium">{s.key}</p><p className="text-xs text-muted-foreground">{s.description}</p></div>
                <Textarea className="min-h-[40px] font-mono text-xs md:col-span-1" value={text} onChange={(e) => setDrafts({ ...drafts, [s.key]: e.target.value })} aria-label={s.key} />
                <div className="flex items-start">{drafts[s.key] !== undefined && <Button size="sm" loading={save.isPending && save.variables?.key === s.key} onClick={() => {
                  try { setErr(null); save.mutate({ key: s.key, value: JSON.parse(drafts[s.key]) }); } catch { setErr(t("md.invalidJson")); }
                }}>{t("common.save")}</Button>}</div>
              </div>
            );
          })}
        </CardBody>
      )}
    </Card>
  );
}

function RatesTab() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const rates = useQuery({ queryKey: ["rates"], queryFn: () => api.get<{ id: number; currency: string; rate_to_uzs: string; as_of: string; source: string }[]>("/exchange-rates") });
  const [f, setF] = useState({ currency: "USD", rate_to_uzs: "", as_of: new Date().toISOString().slice(0, 10), source: "" });
  const add = useMutation({ mutationFn: () => api.post("/admin/exchange-rates", { ...f, as_of: `${f.as_of}T00:00:00+05:00` }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rates"] }); setF({ ...f, rate_to_uzs: "", source: "" }); } });
  return (
    <Card>
      <CardHeader title={t("admin.tab.rates")} description={t("admin.ratesHint")} />
      <CardBody className="grid gap-3 md:grid-cols-5">
        <Field label={t("supplierDash.currency")}><Input maxLength={3} value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value.toUpperCase() })} /></Field>
        <Field label={t("admin.rate")}><Input type="number" step="any" value={f.rate_to_uzs} onChange={(e) => setF({ ...f, rate_to_uzs: e.target.value })} /></Field>
        <Field label={t("admin.asOf")}><Input type="date" value={f.as_of} onChange={(e) => setF({ ...f, as_of: e.target.value })} /></Field>
        <Field label={t("common.source")}><Input value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} placeholder="cbu.uz" /></Field>
        <div className="flex items-end"><Button onClick={() => add.mutate()} loading={add.isPending} disabled={!f.rate_to_uzs || f.source.length < 2}>{t("common.add")}</Button></div>
        {add.error && <Alert tone="red" className="md:col-span-5">{(add.error as Error).message}</Alert>}
      </CardBody>
      {rates.data?.length ? (
        <Table><thead><tr><Th>{t("supplierDash.currency")}</Th><Th className="text-right">{t("admin.rate")}</Th><Th>{t("admin.asOf")}</Th><Th>{t("common.source")}</Th></tr></thead>
          <tbody>{rates.data.map((r) => <tr key={r.id}><Td>{r.currency}</Td><Td className="text-right">{fmtNum(r.rate_to_uzs, lang, 4)}</Td><Td className="text-xs">{fmtDate(r.as_of, lang)}</Td><Td className="text-xs">{r.source}</Td></tr>)}</tbody></Table>
      ) : <EmptyState title={t("admin.noRates")} />}
    </Card>
  );
}

function AuditTab() {
  const { t, lang } = useI18n();
  const [page, setPage] = useState(1);
  const [type, setType] = useState("");
  const q = useQuery({ queryKey: ["audit", page, type], queryFn: () => api.get<Page<{ id: number; user_id: number | null; action: string; entity_type: string; entity_id: string | null; changes: unknown; ip_address: string | null; created_at: string }>>("/admin/audit-logs", { page, page_size: 25, entity_type: type || undefined }) });
  return (
    <Card>
      <CardHeader title={t("admin.tab.audit")} action={<Input className="w-56" placeholder={t("admin.entityType")} value={type} onChange={(e) => { setType(e.target.value); setPage(1); }} aria-label={t("admin.entityType")} />} />
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState /> : (
        <div className="px-2">
          <Table><thead><tr><Th>{t("admin.time")}</Th><Th>{t("admin.user")}</Th><Th>{t("admin.action")}</Th><Th>{t("admin.entity")}</Th><Th>{t("admin.changes")}</Th><Th>IP</Th></tr></thead>
            <tbody>{q.data.items.map((a) => (
              <tr key={a.id}><Td className="whitespace-nowrap text-xs">{fmtDate(a.created_at, lang, true)}</Td><Td className="text-xs">{a.user_id ?? "—"}</Td>
                <Td><Badge tone="slate">{a.action}</Badge></Td><Td className="text-xs">{a.entity_type} {a.entity_id && `#${a.entity_id}`}</Td>
                <Td className="max-w-md truncate font-mono text-[11px]" title={JSON.stringify(a.changes)}>{a.changes ? JSON.stringify(a.changes) : "—"}</Td><Td className="text-xs">{a.ip_address ?? "—"}</Td></tr>))}</tbody></Table>
          <Pagination page={page} pageSize={25} total={q.data.total} onPage={setPage} />
        </div>
      )}
    </Card>
  );
}

function DemoTab() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["demo-counts"], queryFn: () => api.get<Record<string, number>>("/admin/demo-data") });
  const [confirm, setConfirm] = useState(false);
  const purge = useMutation({ mutationFn: () => api.del("/admin/demo-data"), onSuccess: () => { setConfirm(false); qc.invalidateQueries(); } });
  return (
    <Card>
      <CardHeader title={t("admin.tab.demo")} description={t("admin.demoHint")} />
      <CardBody className="space-y-3">
        {q.isLoading ? <LoadingState /> : (
          <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">{Object.entries(q.data ?? {}).map(([k, v]) => (
            <div key={k} className="rounded-md bg-muted p-3"><p className="text-xs text-muted-foreground">{k}</p><p className="text-lg font-semibold">{v}</p></div>))}</div>
        )}
        <Button variant="destructive" onClick={() => setConfirm(true)} disabled={!Object.values(q.data ?? {}).some(Boolean)}><Trash2 className="h-4 w-4" />{t("admin.purge")}</Button>
        {purge.isSuccess && <Alert tone="green">{t("admin.purged")}</Alert>}
        {purge.error && <Alert tone="red">{(purge.error as Error).message}</Alert>}
      </CardBody>
      <ConfirmDialog open={confirm} destructive title={t("admin.purgeTitle")} message={t("admin.purgeMsg")} onCancel={() => setConfirm(false)}
        onConfirm={() => purge.mutate()} loading={purge.isPending} />
    </Card>
  );
}

function PlansTab() {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["plans"], queryFn: () => api.get<{ id: number; code: string; name: string; audience: string; features: Record<string, unknown>; is_active: boolean }[]>("/admin/subscription-plans") });
  return (
    <Card>
      <CardHeader title={t("admin.tab.plans")} description={t("admin.plansHint")} />
      {q.isLoading ? <LoadingState /> : (
        <Table><thead><tr><Th>{t("md.code")}</Th><Th>{t("common.name")}</Th><Th>{t("admin.audience")}</Th><Th>{t("admin.features")}</Th></tr></thead>
          <tbody>{q.data?.map((p) => <tr key={p.id}><Td className="font-mono text-xs">{p.code}</Td><Td>{p.name}</Td><Td className="text-xs">{p.audience}</Td>
            <Td className="font-mono text-[11px]">{JSON.stringify(p.features)}</Td></tr>)}</tbody></Table>
      )}
    </Card>
  );
}
