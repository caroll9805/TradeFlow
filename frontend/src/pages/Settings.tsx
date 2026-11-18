import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n, type Lang } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import { fmtDate } from "@/lib/format";
import { Alert, Badge, Button, Card, CardBody, CardHeader, EmptyState, Field, Input, PageHeader, Select, Switch } from "@/components/ui";

export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { user, refreshMe, logout } = useAuth();
  const { includeSimulated, setIncludeSimulated } = usePrefs();
  const qc = useQueryClient();
  const [name, setName] = useState(user?.full_name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const profile = useMutation({ mutationFn: () => api.patch("/auth/me", { full_name: name, phone: phone || null, locale: lang }), onSuccess: () => refreshMe() });
  const password = useMutation({ mutationFn: () => api.post("/auth/me/password", pw), onSuccess: async () => { await logout(); } });
  const notes = useQuery({ queryKey: ["notifications"], queryFn: () => api.get<{ id: number; title: string; link: string | null; read_at: string | null; created_at: string }[]>("/notifications") });
  const read = useMutation({ mutationFn: (id: number) => api.post(`/notifications/${id}/read`), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });
  if (!user) return null;
  return (
    <div className="space-y-5">
      <PageHeader title={t("settings.title")} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title={t("settings.profile")} description={`${user.email} · ${user.role_name ? (lang === "ru" ? user.role_name.ru : user.role_name.uz) : user.role}`} />
          <CardBody className="space-y-3">
            <Field label={t("auth.fullName")}><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label={t("auth.phone")}><Input value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
            <Field label={t("nav.language")}><Select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
              <option value="uz">O'zbekcha</option><option value="ru">Русский</option><option value="en">English</option></Select></Field>
            <p className="text-xs text-muted-foreground">{t("settings.orgs")}: {user.organizations.map((o) => o.name).join(", ") || "—"}</p>
            <Button onClick={() => profile.mutate()} loading={profile.isPending}>{t("common.save")}</Button>
            {profile.isSuccess && <Alert tone="green">{t("settings.saved")}</Alert>}
            {profile.error && <Alert tone="red">{(profile.error as Error).message}</Alert>}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title={t("settings.security")} description={t("settings.passwordHint")} />
          <CardBody className="space-y-3">
            <Field label={t("settings.currentPassword")}><Input type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
            <Field label={t("settings.newPassword")} hint={t("validation.password")}><Input type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
            <Button onClick={() => password.mutate()} loading={password.isPending} disabled={!pw.current_password || pw.new_password.length < 8}>{t("settings.changePassword")}</Button>
            {password.error && <Alert tone="red">{(password.error as Error).message}</Alert>}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title={t("settings.data")} />
          <CardBody className="space-y-2">
            <Switch checked={includeSimulated} onChange={setIncludeSimulated} label={t("simulated.toggle")} />
            <p className="text-xs text-muted-foreground">{t("simulated.toggleHint")}</p>
            <p className="text-xs text-muted-foreground">{t("settings.tz")}</p>
          </CardBody>
        </Card>
        <Card id="notifications">
          <CardHeader title={t("nav.notifications")} />
          <CardBody>
            {!notes.data?.length ? <EmptyState /> : (
              <ul className="divide-y divide-border text-sm">{notes.data.map((n) => (
                <li key={n.id} className="flex items-center justify-between gap-2 py-2">
                  <div>{n.link ? <Link to={n.link} className="hover:text-primary">{n.title}</Link> : n.title}
                    <p className="text-xs text-muted-foreground">{fmtDate(n.created_at, lang, true)}</p></div>
                  {n.read_at ? <Badge tone="slate">{t("settings.read")}</Badge> : <Button size="sm" variant="outline" onClick={() => read.mutate(n.id)}>{t("settings.markRead")}</Button>}
                </li>))}</ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
