import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Forecast, HistoryPoint, RegionalPrice } from "@/lib/types";
import { fmtDate, fmtNum, toNum } from "@/lib/format";
import { useI18n } from "@/lib/i18n";

const AXIS = { fontSize: 11, fill: "#64748b" };

export function PriceHistoryChart({ points, forecast, unit }: { points: HistoryPoint[]; forecast?: Forecast; unit: string }) {
  const { t, lang } = useI18n();
  const data: Record<string, number | string | null | [number, number]>[] = points.map((p) => ({
    period: p.period, avg: p.avg, band: [p.min, p.max], estimate: null }));
  if (forecast?.status === "ok" && forecast.forecast?.length && points.length) {
    data[data.length - 1].estimate = points[points.length - 1].avg;
    forecast.forecast.forEach((f) => data.push({ period: f.period, avg: null, band: [f.low, f.high], estimate: f.estimate }));
  }
  return (
    <div className="h-72 w-full" aria-label={t("charts.priceHistory")}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <CartesianGrid stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="period" tickFormatter={(v: unknown) => fmtDate(String(v), lang)} tick={AXIS} minTickGap={24} />
          <YAxis tick={AXIS} tickFormatter={(v: unknown) => fmtNum(v as number, lang)} width={70} domain={["auto", "auto"]} />
          <Tooltip formatter={(v: unknown, name: unknown) => [Array.isArray(v) ? `${fmtNum(v[0], lang)} – ${fmtNum(v[1], lang)}` : fmtNum(v as number, lang), t(`charts.${String(name)}`)]}
            labelFormatter={(v: unknown) => `${fmtDate(String(v), lang)} · UZS/${unit}`} />
          <Area dataKey="band" stroke="none" fill="#0f766e" fillOpacity={0.1} isAnimationActive={false} />
          <Line dataKey="avg" stroke="#0f766e" strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
          <Line dataKey="estimate" stroke="#d97706" strokeDasharray="5 4" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RegionalBarChart({ rows, unit }: { rows: RegionalPrice[]; unit: string }) {
  const { lang, nm, t } = useI18n();
  const data = rows.map((r) => ({ name: nm(r), avg: toNum(r.avg), min: toNum(r.min) }));
  return (
    <div className="w-full" style={{ height: Math.max(180, rows.length * 34) }} aria-label={t("charts.regional")}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20 }}>
          <CartesianGrid stroke="#e2e8f0" horizontal={false} />
          <XAxis type="number" tick={AXIS} tickFormatter={(v: unknown) => fmtNum(v as number, lang)} />
          <YAxis type="category" dataKey="name" tick={AXIS} width={150} />
          <Tooltip formatter={(v: unknown, name: unknown) => [`${fmtNum(v as number, lang)} UZS/${unit}`, t(`charts.${String(name)}`)]} />
          <Bar dataKey="min" fill="#99f6e4" isAnimationActive={false} />
          <Bar dataKey="avg" fill="#0f766e" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CategoryBarChart({ rows }: { rows: { name: string; value: number }[] }) {
  const { t } = useI18n();
  return (
    <div className="h-72 w-full" aria-label={t("charts.offersByCategory")}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 10, right: 20 }}>
          <CartesianGrid stroke="#e2e8f0" horizontal={false} />
          <XAxis type="number" tick={AXIS} allowDecimals={false} />
          <YAxis type="category" dataKey="name" tick={AXIS} width={170} />
          <Tooltip />
          <Bar dataKey="value" name={t("dashboard.activeOffers")} fill="#0f766e" radius={[0, 4, 4, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
