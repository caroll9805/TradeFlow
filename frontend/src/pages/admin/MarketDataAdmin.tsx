import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Pencil, Play, Plus, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Connector, DataSource, Job, Match, Observation, Page, Product } from "@/lib/types";
import { fmtDate, fmtNum } from "@/lib/format";
import { Alert, Badge, Button, Card, CardBody, CardHeader, ConfirmDialog, Dialog, EmptyState, ErrorState, Field, Input, LoadingState,
  PageHeader, Pagination, Select, Switch, Table, Tabs, Td, Textarea, Th } from "@/components/ui";
import { PriceTypeSelect, RegionSelect, UnitSelect } from "@/components/selects";
import { ProvenanceBadge, SimulatedBadge, VerificationBadge } from "@/components/badges";
import { ProductPicker } from "@/components/ProductPicker";

type Tab = "sources" | "connectors" | "import" | "jobs" | "matches" | "observations" | "verification";

export default function MarketDataAdmin() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("sources");
  return (
    <div className="space-y-5">
      <PageHeader title={t("md.title")} description={t("md.subtitle")} />
      <Tabs value={tab} onChange={setTab} items={(["sources", "connectors", "import", "jobs", "matches", "observations", "verification"] as Tab[]).map((v) => ({ value: v, label: t(`md.tab.${v}`) }))} />
      {tab === "sources" && <SourcesTab />}
      {tab === "connectors" && <ConnectorsTab />}
      {tab === "import" && <ImportTab />}
      {tab === "jobs" && <JobsTab />}
      {tab === "matches" && <MatchesTab />}
      {tab === "observations" && <ObservationsTab />}
      {tab === "verification" && <VerificationTab />}
    </div>
  );
}

const useSources = () => useQuery({ queryKey: ["md-sources"], queryFn: () => api.get<DataSource[]>("/market-data/sources") });

function TermsBadge({ s }: { s: string }) {
  const { t } = useI18n();
  return <Badge tone={s === "permitted" ? "green" : s === "not_permitted" ? "red" : s === "pending_review" ? "amber" : "slate"}>{t(`terms.${s}`)}</Badge>;
}

function SourcesTab() {
  const { t, lang } = useI18n();
  const q = useSources();
  const [edit, setEdit] = useState<DataSource | null | "new">(null);
  return (
    <Card>
      <CardHeader title={t("md.tab.sources")} description={t("md.sourcesHint")} action={<Button onClick={() => setEdit("new")}><Plus className="h-4 w-4" />{t("common.add")}</Button>} />
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : (
        <Table>
          <thead><tr><Th>{t("common.name")}</Th><Th>{t("md.type")}</Th><Th>{t("common.provenance")}</Th><Th>{t("md.terms")}</Th><Th>{t("dashboard.reliability")}</Th>
            <Th>{t("md.freshness")}</Th><Th>{t("common.status")}</Th><Th /></tr></thead>
          <tbody>{q.data?.map((s) => (
            <tr key={s.id}>
              <Td><p className="font-medium">{s.name} {s.is_simulated && <SimulatedBadge />}</p><p className="text-xs text-muted-foreground">{s.code}{s.base_url && ` · ${s.base_url}`}</p>
                {s.review_notes && <p className="mt-1 max-w-md text-[11px] text-muted-foreground">{s.review_notes}</p>}</Td>
              <Td className="text-xs">{t(`sourceType.${s.source_type}`)}</Td><Td><ProvenanceBadge kind={s.default_provenance} /></Td>
              <Td><TermsBadge s={s.terms_status} /></Td><Td>{fmtNum(s.reliability_score, lang, 2)}</Td><Td className="text-xs">{s.freshness_hours} h</Td>
              <Td><Badge tone={s.is_active ? "green" : "slate"}>{s.is_active ? t("supplierDash.active") : t("supplierDash.inactive")}</Badge></Td>
              <Td><Button size="sm" variant="ghost" onClick={() => setEdit(s)} aria-label={t("common.edit")}><Pencil className="h-3.5 w-3.5" /></Button></Td>
            </tr>))}</tbody>
        </Table>
      )}
      {edit && <SourceDialog source={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
    </Card>
  );
}

function SourceDialog({ source, onClose }: { source: DataSource | null; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [f, setF] = useState({
    code: source?.code ?? "", name: source?.name ?? "", source_type: source?.source_type ?? "marketplace",
    default_provenance: source?.default_provenance ?? "marketplace_listed", base_url: source?.base_url ?? "", terms_status: source?.terms_status ?? "unknown",
    price_kind: source?.price_kind ?? "", review_notes: source?.review_notes ?? "", reliability_score: String(source?.reliability_score ?? "0.5"),
    freshness_hours: String(source?.freshness_hours ?? 72), is_active: source?.is_active ?? true,
    has_public_api: source?.has_public_api ?? null, requires_auth: source?.requires_auth ?? null, redistribution_allowed: source?.redistribution_allowed ?? null,
  });
  const save = useMutation({
    mutationFn: () => {
      const body = { ...f, base_url: f.base_url || null, price_kind: f.price_kind || null, review_notes: f.review_notes || null, freshness_hours: Number(f.freshness_hours) };
      return source ? api.put(`/market-data/sources/${source.id}`, body) : api.post("/market-data/sources", body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["md-sources"] }); onClose(); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const tri = (k: "has_public_api" | "requires_auth" | "redistribution_allowed") => (
    <Select value={f[k] === null ? "" : f[k] ? "1" : "0"} onChange={(e) => setF({ ...f, [k]: e.target.value === "" ? null : e.target.value === "1" })}>
      <option value="">{t("md.unknown")}</option><option value="1">{t("common.yes")}</option><option value="0">{t("common.no")}</option></Select>);
  return (
    <Dialog open onClose={onClose} wide title={source ? source.name : t("md.newSource")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button><Button onClick={() => save.mutate()} loading={save.isPending}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-3">
        <Field label={t("md.code")}><Input value={f.code} onChange={set("code")} disabled={!!source} /></Field>
        <div className="md:col-span-2"><Field label={t("common.name")}><Input value={f.name} onChange={set("name")} /></Field></div>
        <Field label={t("md.type")}><Select value={f.source_type} onChange={set("source_type")}>
          {["supplier_submission", "marketplace", "official_statistics", "supplier_website", "file_import", "manual", "api", "simulated"].map((s) => <option key={s} value={s}>{t(`sourceType.${s}`)}</option>)}</Select></Field>
        <Field label={t("common.provenance")}><Select value={f.default_provenance} onChange={set("default_provenance")}>
          {["supplier_declared", "marketplace_listed", "official_statistic", "verified_transaction", "estimated", "simulated"].map((s) => <option key={s} value={s}>{t(`provenance.${s}`)}</option>)}</Select></Field>
        <Field label={t("md.terms")} hint={t("md.termsHint")}><Select value={f.terms_status} onChange={set("terms_status")}>
          {["unknown", "pending_review", "permitted", "not_permitted"].map((s) => <option key={s} value={s}>{t(`terms.${s}`)}</option>)}</Select></Field>
        <div className="md:col-span-3"><Field label="URL"><Input type="url" value={f.base_url} onChange={set("base_url")} placeholder="https://" /></Field></div>
        <Field label={t("md.publicApi")}>{tri("has_public_api")}</Field>
        <Field label={t("md.requiresAuth")}>{tri("requires_auth")}</Field>
        <Field label={t("md.redistribution")}>{tri("redistribution_allowed")}</Field>
        <Field label={t("dashboard.reliability")} hint="0–1"><Input type="number" step="0.05" min={0} max={1} value={f.reliability_score} onChange={set("reliability_score")} /></Field>
        <Field label={t("md.freshness") + " (h)"}><Input type="number" min={1} value={f.freshness_hours} onChange={set("freshness_hours")} /></Field>
        <Field label={t("md.priceKind")}><Input value={f.price_kind} onChange={set("price_kind")} placeholder="wholesale / retail / mixed" /></Field>
        <div className="md:col-span-3"><Field label={t("md.reviewNotes")}><Textarea value={f.review_notes} onChange={set("review_notes")} /></Field></div>
        <Switch checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} label={t("supplierDash.active")} />
      </div>
      {save.error && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
    </Dialog>
  );
}

function ConnectorsTab() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["md-connectors"], queryFn: () => api.get<Connector[]>("/market-data/connectors") });
  const [edit, setEdit] = useState<Connector | null | "new">(null);
  const [result, setResult] = useState<Job | null>(null);
  const run = useMutation({ mutationFn: (id: number) => api.post<Job>(`/market-data/connectors/${id}/run`),
    onSuccess: (j) => { setResult(j); qc.invalidateQueries({ queryKey: ["md-connectors"] }); qc.invalidateQueries({ queryKey: ["md-jobs"] }); } });
  return (
    <Card>
      <CardHeader title={t("md.tab.connectors")} description={t("md.connectorsHint")} action={<Button onClick={() => setEdit("new")}><Plus className="h-4 w-4" />{t("common.add")}</Button>} />
      {result && <div className="px-5 pt-4"><Alert tone={result.status === "failed" ? "red" : "green"}>{t("md.jobResult", { s: result.status, c: result.records_collected, r: result.records_rejected })}{result.error && ` — ${result.error}`}</Alert></div>}
      {run.error && <div className="px-5 pt-4"><Alert tone="red">{(run.error as Error).message}</Alert></div>}
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState /> : (
        <Table>
          <thead><tr><Th>{t("common.name")}</Th><Th>{t("md.type")}</Th><Th>{t("common.status")}</Th><Th>{t("md.lastSuccess")}</Th><Th>{t("md.lastFailure")}</Th>
            <Th className="text-right">{t("md.collected")}</Th><Th className="text-right">{t("md.rejected")}</Th><Th>{t("md.frequency")}</Th><Th /></tr></thead>
          <tbody>{q.data.map((c) => (
            <tr key={c.id}>
              <Td><p className="font-medium">{c.name}</p><p className="text-xs text-muted-foreground">{c.data_source}</p>{c.last_error && <p className="max-w-xs text-[11px] text-red-600">{c.last_error}</p>}</Td>
              <Td className="text-xs">{c.connector_type}</Td>
              <Td><Badge tone={c.status === "ok" ? "green" : c.status === "error" ? "red" : "slate"}>{t(`md.cstatus.${c.status}`)}</Badge></Td>
              <Td className="text-xs">{fmtDate(c.last_success_at, lang, true)}</Td><Td className="text-xs">{fmtDate(c.last_failure_at, lang, true)}</Td>
              <Td className="text-right">{fmtNum(c.records_collected_total, lang)}</Td><Td className="text-right">{fmtNum(c.records_rejected_total, lang)}</Td>
              <Td className="text-xs">{c.interval_minutes ? t("md.everyMin", { n: c.interval_minutes }) : t("md.manual")}</Td>
              <Td className="whitespace-nowrap">
                <Button size="sm" variant="ghost" onClick={() => setEdit(c)} aria-label={t("common.edit")}><Pencil className="h-3.5 w-3.5" /></Button>
                {!["file_import", "supplier_submission", "manual_entry"].includes(c.connector_type) &&
                  <Button size="sm" variant="outline" onClick={() => run.mutate(c.id)} loading={run.isPending && run.variables === c.id}><Play className="h-3.5 w-3.5" />{t("md.run")}</Button>}
              </Td>
            </tr>))}</tbody>
        </Table>
      )}
      {edit && <ConnectorDialog connector={edit === "new" ? null : edit} onClose={() => setEdit(null)} />}
    </Card>
  );
}

function ConnectorDialog({ connector, onClose }: { connector: Connector | null; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const sources = useSources();
  const types = useQuery({ queryKey: ["connector-types"], queryFn: () => api.get<{ type: string; description: string; config_schema: Record<string, unknown>; requires_terms_permission: boolean }[]>("/connector-types") });
  const [f, setF] = useState({ name: connector?.name ?? "", data_source_id: connector?.data_source_id ?? ("" as number | ""), connector_type: connector?.connector_type ?? "http_json",
    config: JSON.stringify(connector?.config ?? {}, null, 2), interval_minutes: connector?.interval_minutes ? String(connector.interval_minutes) : "", is_enabled: connector?.is_enabled ?? false });
  const [jsonErr, setJsonErr] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => {
      let config: unknown;
      try { config = JSON.parse(f.config || "{}"); setJsonErr(null); } catch { setJsonErr(t("md.invalidJson")); throw new Error(t("md.invalidJson")); }
      const body = { name: f.name, data_source_id: f.data_source_id, connector_type: f.connector_type, config, interval_minutes: f.interval_minutes ? Number(f.interval_minutes) : null, is_enabled: f.is_enabled };
      return connector ? api.put(`/market-data/connectors/${connector.id}`, body) : api.post("/market-data/connectors", body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["md-connectors"] }); onClose(); },
  });
  const type = types.data?.find((x) => x.type === f.connector_type);
  return (
    <Dialog open onClose={onClose} wide title={connector ? connector.name : t("md.newConnector")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button><Button onClick={() => save.mutate()} loading={save.isPending} disabled={!f.name || !f.data_source_id}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t("common.name")}><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label={t("common.source")}><Select value={f.data_source_id} onChange={(e) => setF({ ...f, data_source_id: e.target.value ? Number(e.target.value) : "" })}>
          <option value="">{t("common.select")}</option>{sources.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Field label={t("md.type")} hint={type?.description}><Select value={f.connector_type} onChange={(e) => setF({ ...f, connector_type: e.target.value })}>
          {types.data?.map((x) => <option key={x.type} value={x.type}>{x.type}</option>)}</Select></Field>
        <Field label={t("md.frequency")} hint={t("md.frequencyHint")}><Input type="number" min={15} value={f.interval_minutes} onChange={(e) => setF({ ...f, interval_minutes: e.target.value })} /></Field>
        <div className="md:col-span-2"><Field label={t("md.config")} error={jsonErr ?? undefined} hint={type ? `${t("md.configKeys")}: ${Object.keys(type.config_schema).join(", ") || "—"}` : undefined}>
          <Textarea className="min-h-[160px] font-mono text-xs" value={f.config} onChange={(e) => setF({ ...f, config: e.target.value })} /></Field></div>
        <Switch checked={f.is_enabled} onChange={(v) => setF({ ...f, is_enabled: v })} label={t("md.enabled")} />
      </div>
      {type?.requires_terms_permission && <Alert className="mt-3">{t("md.termsRequired")}</Alert>}
      {save.error && !jsonErr && <Alert tone="red" className="mt-3">{(save.error as Error).message}</Alert>}
    </Dialog>
  );
}

function ImportTab() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const sources = useSources();
  const [file, setFile] = useState<File | null>(null);
  const [src, setSrc] = useState<number | "">("");
  const [type, setType] = useState("observation");
  const [create, setCreate] = useState(false);
  const up = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("file", file!);
      fd.append("data_source_id", String(src));
      fd.append("record_type", type);
      fd.append("allow_create_products", String(create));
      return api.upload<Job>("/market-data/import", fd);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["md-jobs"] }); qc.invalidateQueries({ queryKey: ["md-matches"] }); },
  });
  const j = up.data;
  return (
    <Card>
      <CardHeader title={t("md.tab.import")} description={t("md.importHint")}
        action={<a href="/sample_price_list.csv" download className="inline-flex items-center gap-1 text-xs text-primary"><Download className="h-3.5 w-3.5" />{t("md.template")}</a>} />
      <CardBody className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Field label={t("md.file")} hint=".csv / .xlsx"><Input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Field label={t("common.source")}><Select value={src} onChange={(e) => setSrc(e.target.value ? Number(e.target.value) : "")}>
            <option value="">{t("common.select")}</option>{sources.data?.filter((s) => s.is_active).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          <Field label={t("md.recordType")} hint={t("md.recordTypeHint")}><Select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="observation">{t("md.asObservations")}</option><option value="offer">{t("md.asOffers")}</option></Select></Field>
          <div className="flex items-end pb-2"><Switch checked={create} onChange={setCreate} label={t("md.allowCreate")} /></div>
        </div>
        <Button onClick={() => up.mutate()} loading={up.isPending} disabled={!file || !src}><Upload className="h-4 w-4" />{t("md.upload")}</Button>
        {up.error && <Alert tone="red">{(up.error as Error).message}</Alert>}
        {j && <Alert tone={j.status === "failed" ? "red" : j.status === "partial" ? "amber" : "green"}>
          {t("md.importResult", { seen: j.records_seen, c: j.records_collected, d: j.records_duplicate, p: j.records_pending_review, r: j.records_rejected })}
          {j.error && <p className="mt-1">{j.error}</p>} <JobLogsLink job={j} /></Alert>}
      </CardBody>
    </Card>
  );
}

function JobLogsLink({ job }: { job: Job }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const logs = useQuery({ queryKey: ["md-logs", job.id], enabled: open,
    queryFn: () => api.get<{ id: number; level: string; row_number: number | null; message: string }[]>(`/market-data/jobs/${job.id}/logs`) });
  return (
    <>
      <button className="ml-1 underline" onClick={() => setOpen(true)}>{t("md.logs")}</button>
      <Dialog open={open} onClose={() => setOpen(false)} wide title={t("md.logsTitle", { id: job.id })}>
        {logs.isLoading ? <LoadingState /> : !logs.data?.length ? <EmptyState /> : (
          <Table><thead><tr><Th>{t("md.row")}</Th><Th>{t("md.level")}</Th><Th>{t("md.message")}</Th></tr></thead>
            <tbody>{logs.data.map((l) => <tr key={l.id}><Td>{l.row_number ?? "—"}</Td><Td><Badge tone={l.level === "error" ? "red" : l.level === "warning" ? "amber" : "slate"}>{l.level}</Badge></Td><Td className="text-xs">{l.message}</Td></tr>)}</tbody></Table>
        )}
      </Dialog>
    </>
  );
}

function JobsTab() {
  const { t, lang } = useI18n();
  const [page, setPage] = useState(1);
  const q = useQuery({ queryKey: ["md-jobs", page], queryFn: () => api.get<Page<Job>>("/market-data/jobs", { page, page_size: 20 }) });
  return (
    <Card>
      <CardHeader title={t("md.tab.jobs")} />
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState /> : (
        <div className="px-2">
          <Table>
            <thead><tr><Th>#</Th><Th>{t("common.source")}</Th><Th>{t("md.trigger")}</Th><Th>{t("common.status")}</Th><Th>{t("md.started")}</Th>
              <Th className="text-right">{t("md.seen")}</Th><Th className="text-right">{t("md.collected")}</Th><Th className="text-right">{t("md.duplicates")}</Th>
              <Th className="text-right">{t("md.pending")}</Th><Th className="text-right">{t("md.rejected")}</Th><Th /></tr></thead>
            <tbody>{q.data.items.map((j) => (
              <tr key={j.id}><Td>{j.id}</Td><Td className="text-xs">{j.data_source}{j.file_name && <p className="text-muted-foreground">{j.file_name}</p>}</Td>
                <Td className="text-xs">{j.trigger}</Td>
                <Td><Badge tone={j.status === "succeeded" ? "green" : j.status === "failed" ? "red" : j.status === "partial" ? "amber" : "slate"}>{j.status}</Badge>
                  {j.error && <p className="max-w-xs text-[11px] text-red-600">{j.error}</p>}</Td>
                <Td className="text-xs">{fmtDate(j.started_at, lang, true)}</Td><Td className="text-right">{j.records_seen}</Td><Td className="text-right">{j.records_collected}</Td>
                <Td className="text-right">{j.records_duplicate}</Td><Td className="text-right">{j.records_pending_review}</Td><Td className="text-right">{j.records_rejected}</Td>
                <Td className="text-xs"><JobLogsLink job={j} /></Td></tr>))}</tbody>
          </Table>
          <Pagination page={page} pageSize={20} total={q.data.total} onPage={setPage} />
        </div>
      )}
    </Card>
  );
}

function MatchesTab() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const q = useQuery({ queryKey: ["md-matches", page], queryFn: () => api.get<Page<Match>>("/market-data/matches", { page, page_size: 20 }) });
  const [assign, setAssign] = useState<Match | null>(null);
  const [assignTo, setAssignTo] = useState<Product | null>(null);
  const decide = useMutation({ mutationFn: ({ id, action, product_id }: { id: number; action: string; product_id?: number }) => api.post(`/market-data/matches/${id}`, { action, product_id }),
    onSuccess: () => { setAssign(null); setAssignTo(null); qc.invalidateQueries({ queryKey: ["md-matches"] }); } });
  return (
    <Card>
      <CardHeader title={t("md.tab.matches")} description={t("md.matchesHint")} />
      {decide.error && <div className="px-5 pt-3"><Alert tone="red">{(decide.error as Error).message}</Alert></div>}
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState title={t("md.noMatches")} /> : (
        <div className="px-2">
          <Table>
            <thead><tr><Th>{t("md.originalName")}</Th><Th>{t("md.candidate")}</Th><Th className="text-right">{t("md.confidence")}</Th><Th>{t("md.reasons")}</Th><Th>{t("md.record")}</Th><Th /></tr></thead>
            <tbody>{q.data.items.map((m) => (
              <tr key={m.id}>
                <Td className="font-medium">{m.original_name}</Td>
                <Td>{m.candidate ? <Link to={`/products/${m.candidate.id}`} className="hover:text-primary">{m.candidate.name}</Link> : "—"}</Td>
                <Td className="text-right">{m.score !== null ? Number(m.score).toFixed(2) : "—"}</Td>
                <Td className="text-xs">{m.reasons.join("; ")}</Td>
                <Td className="max-w-xs text-[11px] text-muted-foreground">{Object.entries(m.raw_record).filter(([, v]) => v !== "" && v !== null).map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}</Td>
                <Td className="whitespace-nowrap">
                  {m.candidate && <Button size="sm" onClick={() => decide.mutate({ id: m.id, action: "accept" })}>{t("md.accept")}</Button>}
                  <Button size="sm" variant="outline" className="ml-1" onClick={() => setAssign(m)}>{t("md.assign")}</Button>
                  <Button size="sm" variant="ghost" className="ml-1 text-destructive" onClick={() => decide.mutate({ id: m.id, action: "reject" })}>{t("md.reject")}</Button>
                </Td>
              </tr>))}</tbody>
          </Table>
          <Pagination page={page} pageSize={20} total={q.data.total} onPage={setPage} />
        </div>
      )}
      <Dialog open={!!assign} onClose={() => setAssign(null)} title={t("md.assignTitle", { n: assign?.original_name ?? "" })}
        footer={<><Button variant="outline" onClick={() => setAssign(null)}>{t("common.cancel")}</Button>
          <Button disabled={!assignTo} loading={decide.isPending} onClick={() => assign && assignTo && decide.mutate({ id: assign.id, action: "assign", product_id: assignTo.id })}>{t("md.assign")}</Button></>}>
        <ProductPicker value={assignTo} onChange={setAssignTo} />
        <p className="mt-2 text-xs text-muted-foreground">{t("md.assignHint")}</p>
      </Dialog>
    </Card>
  );
}

function ObservationsTab() {
  const { t, nm, lang } = useI18n();
  const qc = useQueryClient();
  const sources = useSources();
  const [page, setPage] = useState(1);
  const [src, setSrc] = useState<number | "">("");
  const [ver, setVer] = useState("");
  const [sim, setSim] = useState("");
  const [adding, setAdding] = useState(false);
  const params = { page, page_size: 20, source_id: src || undefined, verification_status: ver || undefined, simulated: sim === "" ? undefined : sim };
  const q = useQuery({ queryKey: ["md-observations", params], queryFn: () => api.get<Page<Observation>>("/market-data/observations", params) });
  const act = useMutation({ mutationFn: ({ id, path, query }: { id: number; path: string; query: Record<string, string | boolean> }) => api.post(`/market-data/observations/${id}/${path}`, undefined, query),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["md-observations"] }) });
  return (
    <Card>
      <CardHeader title={t("md.tab.observations")} description={t("md.observationsHint")} action={<Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" />{t("md.manualEntry")}</Button>} />
      <div className="grid gap-2 px-5 pt-4 md:grid-cols-3">
        <Select value={src} onChange={(e) => { setSrc(e.target.value ? Number(e.target.value) : ""); setPage(1); }} aria-label={t("common.source")}>
          <option value="">{t("md.allSources")}</option>{sources.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
        <Select value={ver} onChange={(e) => { setVer(e.target.value); setPage(1); }} aria-label={t("compare.verification")}>
          <option value="">{t("md.anyVerification")}</option>{["unverified", "verified", "rejected"].map((v) => <option key={v} value={v}>{t(`verification.${v}`)}</option>)}</Select>
        <Select value={sim} onChange={(e) => { setSim(e.target.value); setPage(1); }} aria-label={t("simulated.badge")}>
          <option value="">{t("md.realAndSim")}</option><option value="false">{t("md.realOnly")}</option><option value="true">{t("md.simOnly")}</option></Select>
      </div>
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? <EmptyState /> : (
        <div className="px-2">
          <Table>
            <thead><tr><Th>{t("common.product")}</Th><Th>{t("common.region")}</Th><Th className="text-right">{t("obs.original")}</Th><Th className="text-right">UZS/base</Th>
              <Th>{t("common.provenance")}</Th><Th>{t("obs.observed")}</Th><Th>{t("obs.quality")}</Th><Th /></tr></thead>
            <tbody>{q.data.items.map((o) => (
              <tr key={o.id}>
                <Td><Link to={`/products/${o.product_id}`} className="hover:text-primary">{o.product_name}</Link><p className="text-[11px] text-muted-foreground">{o.supplier_name ?? "—"} · {o.data_source?.name}</p></Td>
                <Td className="text-xs">{nm(o.region)}</Td>
                <Td className="whitespace-nowrap text-right text-xs">{fmtNum(o.original_price, lang)} {o.original_currency}/{o.original_unit_text}</Td>
                <Td className="text-right">{fmtNum(o.normalized_price_uzs, lang)}</Td>
                <Td><div className="flex flex-wrap gap-1"><ProvenanceBadge kind={o.provenance_kind} /><VerificationBadge status={o.verification_status} />{o.is_simulated && <SimulatedBadge />}</div></Td>
                <Td className="text-xs">{fmtDate(o.observed_at, lang)}</Td>
                <Td className="text-xs">{fmtNum(o.quality_score, lang, 2)}{o.quality_flags.length > 0 && <p className="text-[10px] text-muted-foreground">{o.quality_flags.join(", ")}</p>}
                  {o.is_outlier && <Badge tone="red">{t("obs.outlier")}</Badge>}</Td>
                <Td className="whitespace-nowrap">
                  {o.verification_status !== "verified" && <Button size="sm" variant="outline" onClick={() => act.mutate({ id: o.id, path: "verification", query: { status: "verified" } })}>{t("md.verify")}</Button>}
                  {o.verification_status !== "rejected" && <Button size="sm" variant="ghost" onClick={() => act.mutate({ id: o.id, path: "verification", query: { status: "rejected" } })}>{t("md.reject")}</Button>}
                  <Button size="sm" variant="ghost" onClick={() => act.mutate({ id: o.id, path: "outlier", query: { is_outlier: !o.is_outlier } })}>{o.is_outlier ? t("md.unmarkOutlier") : t("md.markOutlier")}</Button>
                </Td>
              </tr>))}</tbody>
          </Table>
          <Pagination page={page} pageSize={20} total={q.data.total} onPage={setPage} />
        </div>
      )}
      {adding && <ManualObservationDialog onClose={() => setAdding(false)} />}
    </Card>
  );
}

function ManualObservationDialog({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const sources = useSources();
  const [product, setProduct] = useState<Product | null>(null);
  const [f, setF] = useState({ price: "", currency: "UZS", unit_id: "" as number | "", region_id: "" as number | "", price_type: "retail",
    data_source_id: "" as number | "", observed_at: new Date().toISOString().slice(0, 10), source_url: "" });
  const m = useMutation({
    mutationFn: () => api.post("/market-data/observations", { ...f, product_id: product?.id, observed_at: `${f.observed_at}T12:00:00+05:00`, source_url: f.source_url || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["md-observations"] }); onClose(); },
  });
  return (
    <Dialog open onClose={onClose} wide title={t("md.manualEntry")}
      footer={<><Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
        <Button onClick={() => m.mutate()} loading={m.isPending} disabled={!product || !f.price || !f.unit_id || !f.region_id || !f.data_source_id}>{t("common.save")}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="md:col-span-2"><Field label={t("common.product")}><ProductPicker value={product} onChange={setProduct} /></Field></div>
        <Field label={t("supplierDash.price")}><Input type="number" min={0} step="any" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} /></Field>
        <Field label={t("supplierDash.currency")}><Select value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value })}>{["UZS", "USD", "EUR", "RUB"].map((c) => <option key={c}>{c}</option>)}</Select></Field>
        <Field label={t("common.unit")}><UnitSelect value={f.unit_id} onChange={(v) => setF({ ...f, unit_id: v })} /></Field>
        <Field label={t("common.region")}><RegionSelect value={f.region_id} onChange={(v) => setF({ ...f, region_id: v })} allLabel={t("common.select")} /></Field>
        <Field label={t("common.priceType")}><PriceTypeSelect value={f.price_type} onChange={(v) => setF({ ...f, price_type: v || "retail" })} /></Field>
        <Field label={t("common.source")}><Select value={f.data_source_id} onChange={(e) => setF({ ...f, data_source_id: e.target.value ? Number(e.target.value) : "" })}>
          <option value="">{t("common.select")}</option>{sources.data?.filter((s) => !s.is_simulated).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Field label={t("obs.observed")}><Input type="date" value={f.observed_at} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setF({ ...f, observed_at: e.target.value })} /></Field>
        <Field label={t("supplierDash.sourceUrl")} hint={t("md.sourceUrlHint")}><Input type="url" value={f.source_url} onChange={(e) => setF({ ...f, source_url: e.target.value })} /></Field>
      </div>
      {m.error && <Alert tone="red" className="mt-3">{(m.error as Error).message}</Alert>}
    </Dialog>
  );
}

function VerificationTab() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["md-verification"], queryFn: () => api.get<{ id: number; target_type: string; target_id: number; target_name: string | null; evidence: string | null; created_at: string }[]>("/market-data/verification-requests") });
  const [decision, setDecision] = useState<{ id: number; name: string; status: "verified" | "rejected" } | null>(null);
  const decide = useMutation({ mutationFn: (d: { id: number; status: string }) => api.post(`/suppliers/${d.id}/verification`, { status: d.status }),
    onSuccess: () => { setDecision(null); qc.invalidateQueries({ queryKey: ["md-verification"] }); } });
  return (
    <Card>
      <CardHeader title={t("md.tab.verification")} description={t("md.verificationHint")} />
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState /> : (
        <Table>
          <thead><tr><Th>{t("common.supplier")}</Th><Th>{t("supplierDash.evidence")}</Th><Th>{t("procurement.created")}</Th><Th /></tr></thead>
          <tbody>{q.data.map((r) => (
            <tr key={r.id}><Td><Link to={`/suppliers/${r.target_id}`} className="font-medium hover:text-primary">{r.target_name}</Link></Td>
              <Td className="max-w-md text-xs">{r.evidence || "—"}</Td><Td className="text-xs">{fmtDate(r.created_at, lang)}</Td>
              <Td className="whitespace-nowrap"><Button size="sm" onClick={() => setDecision({ id: r.target_id, name: r.target_name ?? "", status: "verified" })}>{t("supplier.verify")}</Button>
                <Button size="sm" variant="ghost" className="ml-1 text-destructive" onClick={() => setDecision({ id: r.target_id, name: r.target_name ?? "", status: "rejected" })}>{t("md.reject")}</Button></Td></tr>))}</tbody>
        </Table>
      )}
      <ConfirmDialog open={!!decision} title={t("supplier.verifyTitle")} message={t("supplier.verifyMessage", { s: decision?.name ?? "", st: t(`verification.${decision?.status ?? "verified"}`) })}
        onCancel={() => setDecision(null)} onConfirm={() => decision && decide.mutate(decision)} loading={decide.isPending} destructive={decision?.status === "rejected"} />
    </Card>
  );
}
