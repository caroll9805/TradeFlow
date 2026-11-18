import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Cpu, Send, User as UserIcon } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { usePrefs } from "@/lib/prefs";
import type { AssistantAnswer } from "@/lib/types";
import { fmtDate } from "@/lib/format";
import { Alert, Badge, Button, Card, CardBody, Input, PageHeader } from "@/components/ui";
import { ProvenanceBadge } from "@/components/badges";

interface Turn { q: string; a?: AssistantAnswer; error?: string }

export default function Assistant() {
  const { t, lang } = useI18n();
  const { includeSimulated } = usePrefs();
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const end = useRef<HTMLDivElement>(null);
  const status = useQuery({ queryKey: ["assistant-status"], queryFn: () => api.get<{ llm_configured: boolean; provider: string | null; model: string | null }>("/assistant/status") });
  const ask = useMutation({
    mutationFn: (question: string) => api.post<AssistantAnswer>("/assistant/ask", { question, include_simulated: includeSimulated, language: lang }),
    onSuccess: (a, question) => setTurns((ts) => ts.map((x) => (x.q === question && !x.a && !x.error ? { ...x, a } : x))),
    onError: (e, question) => setTurns((ts) => ts.map((x) => (x.q === question && !x.a && !x.error ? { ...x, error: (e as Error).message } : x))),
  });
  useEffect(() => { end.current?.scrollIntoView?.({ behavior: "smooth" }); }, [turns]);
  const send = (question: string) => {
    const s = question.trim();
    if (s.length < 2 || ask.isPending) return;
    setTurns((ts) => [...ts, { q: s }]);
    setQ("");
    ask.mutate(s);
  };
  const examples = [1, 2, 3, 4, 5, 6, 7, 8].map((i) => t(`assistant.example${i}`));

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={t("assistant.title")} description={t("assistant.subtitle")}
        actions={status.data && <Badge tone={status.data.llm_configured ? "green" : "slate"}><Cpu className="h-3 w-3" />
          {status.data.llm_configured ? t("assistant.llmOn", { m: status.data.model ?? status.data.provider ?? "" }) : t("assistant.llmOff")}</Badge>} />
      <Alert tone="blue" className="mb-4">{t("assistant.groundingNote")}</Alert>
      {turns.length === 0 && (
        <Card className="mb-4"><CardBody>
          <p className="mb-3 text-sm font-medium">{t("assistant.try")}</p>
          <div className="flex flex-wrap gap-2">{examples.map((e) => (
            <button key={e} onClick={() => send(e)} className="rounded-full border border-border bg-white px-3 py-1.5 text-left text-xs hover:border-primary hover:text-primary">{e}</button>))}</div>
        </CardBody></Card>
      )}
      <div className="space-y-4" aria-live="polite">
        {turns.map((turn, i) => (
          <div key={i} className="space-y-2">
            <div className="flex justify-end"><div className="flex max-w-[85%] items-start gap-2 rounded-lg bg-primary px-3 py-2 text-sm text-white"><UserIcon className="mt-0.5 h-4 w-4 shrink-0" />{turn.q}</div></div>
            <Card className="max-w-[95%] p-4">
              <div className="flex items-start gap-2">
                <Bot className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div className="min-w-0 flex-1 space-y-2">
                  {!turn.a && !turn.error && <p className="text-sm text-muted-foreground">{t("assistant.thinking")}</p>}
                  {turn.error && <Alert tone="red">{turn.error}</Alert>}
                  {turn.a && <Answer a={turn.a} lang={lang} />}
                </div>
              </div>
            </Card>
          </div>
        ))}
        <div ref={end} />
      </div>
      <form className="sticky bottom-0 mt-4 flex gap-2 bg-slate-50/90 py-3 backdrop-blur" onSubmit={(e) => { e.preventDefault(); send(q); }}>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("assistant.placeholder")} aria-label={t("assistant.placeholder")} maxLength={1000} />
        <Button type="submit" loading={ask.isPending} disabled={q.trim().length < 2}><Send className="h-4 w-4" />{t("assistant.ask")}</Button>
      </form>
    </div>
  );
}

function Answer({ a, lang }: { a: AssistantAnswer; lang: string }) {
  const { t } = useI18n();
  return (
    <>
      <p className="whitespace-pre-wrap text-sm leading-relaxed">{a.answer}</p>
      <div className="flex flex-wrap gap-1">
        <Badge tone={a.mode === "llm" ? "violet" : "slate"}>{a.mode === "llm" ? t("assistant.modeLlm") : t("assistant.modeDet")}</Badge>
        <Badge tone="slate">{t("assistant.intent")}: {a.intent}</Badge>
        {a.entities.regions.map((r) => <Badge key={r.id} tone="blue">{lang === "ru" ? r.name_ru : r.name_uz}</Badge>)}
        {a.entities.product && <Link to={`/products/${a.entities.product.id}`}><Badge tone="green">{t("assistant.openComparison")}: {a.entities.product.name}</Badge></Link>}
      </div>
      {a.entities.alternatives.length > 0 && (
        <p className="text-xs text-muted-foreground">{t("assistant.alsoMatched")}: {a.entities.alternatives.map((p, i) => (
          <span key={p.id}>{i > 0 && ", "}<Link to={`/products/${p.id}`} className="text-primary">{p.name}</Link></span>))}</p>
      )}
      {a.note && <Alert>{a.note}</Alert>}
      {a.sources.length > 0 && (
        <div className="rounded-md bg-slate-50 p-2 text-xs">
          <p className="mb-1 font-medium">{t("assistant.sources")}</p>
          <ul className="space-y-1">{a.sources.map((s) => (
            <li key={s.name} className="flex flex-wrap items-center gap-1">{s.name}{s.kind !== "aggregated" && <ProvenanceBadge kind={s.kind} />}
              {s.latest && <span className="text-muted-foreground">· {t("assistant.latest")}: {fmtDate(s.latest, lang, true)}</span>}
              {s.offers !== undefined && <span className="text-muted-foreground">· {t("catalog.offersN", { n: s.offers })}</span>}</li>))}</ul>
        </div>
      )}
      {a.disclaimers.map((d) => <p key={d} className="text-[11px] text-muted-foreground">⚠ {d}</p>)}
    </>
  );
}
