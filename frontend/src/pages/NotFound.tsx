import { Link } from "react-router-dom";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center gap-3 py-24 text-center">
      <p className="text-5xl font-semibold text-slate-300">404</p>
      <p className="text-sm text-muted-foreground">{t("notFound.text")}</p>
      <Link to="/dashboard"><Button variant="outline">{t("notFound.back")}</Button></Link>
    </div>
  );
}
