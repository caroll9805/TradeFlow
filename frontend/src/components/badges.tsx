import { BadgeCheck, Clock, FlaskConical, ShieldAlert, ShieldQuestion } from "lucide-react";
import { Badge } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { ageHours } from "@/lib/format";

export function VerificationBadge({ status }: { status: string }) {
  const { t } = useI18n();
  if (status === "verified") return <Badge tone="green"><BadgeCheck className="h-3 w-3" />{t("verification.verified")}</Badge>;
  if (status === "pending") return <Badge tone="amber"><Clock className="h-3 w-3" />{t("verification.pending")}</Badge>;
  if (status === "rejected") return <Badge tone="red"><ShieldAlert className="h-3 w-3" />{t("verification.rejected")}</Badge>;
  return <Badge tone="slate"><ShieldQuestion className="h-3 w-3" />{t("verification.unverified")}</Badge>;
}

const PROV_TONE: Record<string, "blue" | "violet" | "green" | "amber" | "red" | "slate"> = {
  supplier_declared: "blue", marketplace_listed: "violet", official_statistic: "green", verified_transaction: "green",
  estimated: "amber", simulated: "red",
};
export function ProvenanceBadge({ kind }: { kind: string }) {
  const { t } = useI18n();
  return <Badge tone={PROV_TONE[kind] ?? "slate"} title={t(`provenance.${kind}.hint`)}>{t(`provenance.${kind}`)}</Badge>;
}

export function SimulatedBadge() {
  const { t } = useI18n();
  return <Badge tone="red" title={t("simulated.hint")}><FlaskConical className="h-3 w-3" />{t("simulated.badge")}</Badge>;
}

export function FreshnessBadge({ updatedAt, thresholdHours }: { updatedAt: string | null; thresholdHours: number }) {
  const { t } = useI18n();
  const h = ageHours(updatedAt);
  if (h === null) return <Badge tone="slate">{t("freshness.unknown")}</Badge>;
  const label = h < 24 ? t("freshness.hours", { n: Math.max(1, Math.round(h)) }) : t("freshness.days", { n: Math.round(h / 24) });
  return <Badge tone={h <= thresholdHours ? "green" : "amber"} title={h > thresholdHours ? t("freshness.staleHint") : undefined}>
    {h <= thresholdHours ? label : `${t("freshness.stale")} · ${label}`}
  </Badge>;
}

export function PriceTypeBadge({ type }: { type: string }) {
  const { t } = useI18n();
  return <Badge tone="slate">{t(`priceType.${type}`)}</Badge>;
}
