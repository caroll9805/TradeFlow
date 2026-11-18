import { useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useRegions } from "@/lib/hooks";
import { Alert, Button, Card, Field, Input, Select } from "@/components/ui";
import { LanguageSwitcher, Logo } from "@/components/Layout";

function Shell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-10">
      <div className="mb-6 flex w-full max-w-md items-center justify-between"><Logo /><LanguageSwitcher /></div>
      <Card className="w-full max-w-md p-6">
        <h1 className="mb-5 text-lg font-semibold">{title}</h1>
        {children}
      </Card>
    </div>
  );
}

export function Login() {
  const { t } = useI18n();
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [error, setError] = useState<string | null>(null);
  const schema = z.object({ email: z.string().email(t("validation.email")), password: z.string().min(1, t("validation.required")) });
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (v) => {
    setError(null);
    try {
      await login(v.email, v.password);
      nav(loc.state?.from ?? "/dashboard", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  });

  return (
    <Shell title={t("auth.loginTitle")}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label={t("auth.email")} error={errors.email?.message} htmlFor="email">
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
        </Field>
        <Field label={t("auth.password")} error={errors.password?.message} htmlFor="password">
          <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
        </Field>
        {error && <Alert tone="red">{error}</Alert>}
        <Button type="submit" className="w-full" loading={isSubmitting}>{t("auth.login")}</Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">{t("auth.noAccount")} <Link to="/register" className="font-medium text-primary">{t("nav.register")}</Link></p>
      <Alert tone="blue" className="mt-4">{t("auth.demoHint")}</Alert>
    </Shell>
  );
}

export function Register() {
  const { t, nm, lang } = useI18n();
  const { register: doRegister } = useAuth();
  const { data: regions } = useRegions();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const schema = z.object({
    account_type: z.enum(["buyer", "supplier", "manufacturer"]),
    full_name: z.string().min(2, t("validation.min2")),
    email: z.string().email(t("validation.email")),
    password: z.string().min(8, t("validation.password")).regex(/[A-Za-z]/, t("validation.password")).regex(/\d/, t("validation.password")),
    organization_name: z.string().min(2, t("validation.min2")),
    phone: z.string().max(40).optional(),
    region_id: z.string().optional(),
    tin: z.string().regex(/^(\d{9,14})?$/, t("validation.tin")).optional(),
    supplier_type: z.string().optional(),
  }).refine((v) => v.account_type === "buyer" || !!v.region_id, { path: ["region_id"], message: t("validation.regionRequired") });
  type F = z.infer<typeof schema>;
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<F>({
    resolver: zodResolver(schema), defaultValues: { account_type: "buyer" } });
  const type = watch("account_type");

  const onSubmit = handleSubmit(async (v) => {
    setError(null);
    try {
      await doRegister({ ...v, region_id: v.region_id ? Number(v.region_id) : null, tin: v.tin || null,
        phone: v.phone || null, supplier_type: v.account_type === "buyer" ? null : (v.supplier_type || null), locale: lang });
      nav(v.account_type === "buyer" ? "/dashboard" : "/supplier", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  });

  return (
    <Shell title={t("auth.registerTitle")}>
      <form onSubmit={onSubmit} className="space-y-3" noValidate>
        <Field label={t("auth.accountType")} htmlFor="account_type">
          <Select id="account_type" {...register("account_type")}>
            <option value="buyer">{t("roles.buyer")}</option>
            <option value="supplier">{t("roles.supplier")}</option>
            <option value="manufacturer">{t("roles.manufacturer")}</option>
          </Select>
        </Field>
        <Field label={t("auth.fullName")} error={errors.full_name?.message} htmlFor="full_name"><Input id="full_name" {...register("full_name")} /></Field>
        <Field label={t("auth.email")} error={errors.email?.message} htmlFor="remail"><Input id="remail" type="email" autoComplete="email" {...register("email")} /></Field>
        <Field label={t("auth.password")} error={errors.password?.message} hint={t("validation.password")} htmlFor="rpass">
          <Input id="rpass" type="password" autoComplete="new-password" {...register("password")} />
        </Field>
        <Field label={t("auth.organization")} error={errors.organization_name?.message} htmlFor="org"><Input id="org" {...register("organization_name")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("auth.phone")} htmlFor="phone"><Input id="phone" {...register("phone")} /></Field>
          <Field label={t("auth.tin")} error={errors.tin?.message} htmlFor="tin"><Input id="tin" inputMode="numeric" {...register("tin")} /></Field>
        </div>
        <Field label={t("common.region")} error={errors.region_id?.message} htmlFor="region">
          <Select id="region" {...register("region_id")}>
            <option value="">{t("common.select")}</option>
            {regions?.map((r) => <option key={r.id} value={r.id}>{nm(r)}</option>)}
          </Select>
        </Field>
        {type !== "buyer" && (
          <Field label={t("supplier.type")} htmlFor="stype">
            <Select id="stype" {...register("supplier_type")}>
              {["manufacturer", "wholesaler", "distributor", "importer", "retail", "other"].map((s) => <option key={s} value={s}>{t(`supplierType.${s}`)}</option>)}
            </Select>
          </Field>
        )}
        {type !== "buyer" && <Alert tone="blue">{t("auth.verificationNote")}</Alert>}
        {error && <Alert tone="red">{error}</Alert>}
        <Button type="submit" className="w-full" loading={isSubmitting}>{t("auth.register")}</Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">{t("auth.haveAccount")} <Link to="/login" className="font-medium text-primary">{t("nav.login")}</Link></p>
    </Shell>
  );
}
