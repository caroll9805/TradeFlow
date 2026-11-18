"""AI market assistant.

Pipeline: understand question → resolve entities against the DB → run deterministic tools
(comparison/analytics services) → compose answer from tool output only.
If an LLM provider is configured it is used for understanding & phrasing; otherwise a
deterministic parser and templates are used. Unsupported questions get an honest reply."""
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Product, Region
from app.services import analytics
from app.services.assistant.llm import get_provider
from app.services.comparison import CompareParams, compare_offers, regional_prices
from app.services.text import normalize_text, tokens

INTENTS = ("cheapest", "best_total", "suppliers", "compare_regions", "average_price", "price_increases",
           "price_decreases", "regions_most_offers", "min_quantity", "product_overview")

KEYWORDS: dict[str, list[str]] = {
    "price_increases": ["increase", "rose", "risen", "grow", "qimmatla", "osgan", "oshgan", "ko'tarilgan", "kotarilgan",
                        "подорож", "рост", "вырос", "повыш", "увелич"],
    "price_decreases": ["decrease", "fell", "drop", "cheaper now", "arzonlash", "tushgan", "pasaygan", "подешев",
                        "сниж", "упал", "паден"],
    "regions_most_offers": ["which region", "qaysi viloyat", "какие регион", "какой регион", "в каких регион",
                            "qaysi hudud"],
    "best_total": ["best", "total", "overall", "eng yaxshi", "eng maqbul", "umumiy", "лучш", "итог", "выгодн", "общая стоим"],
    "average_price": ["average", "mean", "ortacha", "o'rtacha", "средн"],
    "compare_regions": ["compare", "solishtir", "taqqosla", "сравни", "сравн", " vs ", "versus"],
    "suppliers": ["supplier", "who sells", "yetkazib", "sotuvchi", "kim sotadi", "поставщик", "кто продает",
                  "кто продаёт", "wholesale", "ulgurji", "оптов"],
    "cheapest": ["cheapest", "lowest", "where can i buy", "eng arzon", "arzon", "qayerdan", "дешев", "дешёв",
                 "где купить", "минимальн", "lowest price"],
}

_QTY = re.compile(r"(?:at least|minimum|min\.?|kamida|не менее|минимум|от)\s*(\d[\d\s.,]*)", re.I)
_QTY_ANY = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(dona|ta|units?|pcs|piece|шт|kg|кг|tonna|ton|т|l|литр|litr|m2|m3|qop|мешк)", re.I)


@dataclass
class Parsed:
    intent: str
    language: str
    product: Product | None = None
    product_alternatives: list[Product] = field(default_factory=list)
    category: Category | None = None
    regions: list[Region] = field(default_factory=list)
    quantity: Decimal | None = None
    price_type: str | None = None


def detect_language(q: str) -> str:
    if re.search(r"[а-яё]", q, re.I):
        uz_cyr = re.search(r"[ўқғҳ]", q, re.I)
        return "uz" if uz_cyr else "ru"
    uz_markers = ["qayer", "narx", "eng ", "qaysi", "viloyat", "yetkaz", "kamida", "o'rtacha", "ortacha", "sotib", "bor",
                  "mahsulot", "toshkent", "samarqand", "arzon"]
    ql = q.lower()
    return "uz" if sum(m in ql for m in uz_markers) >= 1 and not re.search(r"\b(the|where|which|what|how)\b", ql) else "en"


def _stem_match(qtok: str, ptok: str) -> bool:
    if len(ptok) < 3 or len(qtok) < 3:
        return qtok == ptok
    k = max(4, len(ptok) - 2) if len(ptok) > 4 else len(ptok)
    return qtok.startswith(ptok[:k]) or ptok.startswith(qtok[:max(4, len(qtok) - 2)])


def resolve_regions(db: Session, q: str) -> list[Region]:
    qt = normalize_text(q)
    qtoks = qt.split()
    found: list[tuple[int, Region]] = []
    for r in db.scalars(select(Region).order_by(Region.sort_order)).all():
        names = [r.name_uz, r.name_ru, r.name_en, *(r.aliases or [])]
        for n in names:
            nt = normalize_text(n)
            if not nt:
                continue
            ntoks = nt.split()
            if all(any(_stem_match(t, nt_) for t in qtoks) for nt_ in ntoks):
                pos = min((i for i, t in enumerate(qtoks) if _stem_match(t, ntoks[0])), default=999)
                found.append((pos, r))
                break
    # "Tashkent city" vs "Tashkent region": prefer the region only if 'region/viloyat/область' is mentioned
    ids = {r.id for _, r in found}
    city = next((r for _, r in found if r.code == "UZ-TK"), None)
    reg = next((r for _, r in found if r.code == "UZ-TO"), None)
    if city and reg:
        if re.search(r"(region|viloyat|област)", q, re.I):
            found = [(p, r) for p, r in found if r.id != city.id]
        else:
            found = [(p, r) for p, r in found if r.id != reg.id]
    seen, out = set(), []
    for _, r in sorted(found, key=lambda x: x[0]):
        if r.id not in seen and r.id in ids:
            seen.add(r.id)
            out.append(r)
    return out


def resolve_product(db: Session, q: str) -> tuple[Product | None, list[Product], Category | None]:
    qtoks = [t for t in tokens(q) if len(t) >= 3 and not t.isdigit()]
    qall = set(tokens(q))
    best: list[tuple[float, Product]] = []
    for p in db.scalars(select(Product).where(Product.status == "active")).unique().all():
        cand_names = [p.name, *(p.search_terms or [])]
        score = 0.0
        for n in cand_names:
            ptoks = [t for t in tokens(n) if len(t) >= 2]
            words = [t for t in ptoks if len(t) >= 3 and not any(ch.isdigit() for ch in t)]
            specs = [t for t in ptoks if any(ch.isdigit() for ch in t)]
            base = words or ptoks  # specs like "m400"/"50kg" don't dilute the name match...
            if not base:
                continue
            hit = sum(1 for pt in base if any(_stem_match(qt, pt) for qt in qtoks))
            spec_hit = sum(1 for sp in specs if sp in qall)  # ...but they break ties (M400 vs M500)
            score = max(score, hit / len(base) + 0.05 * spec_hit + 0.01 * hit)
        if score >= 0.34:
            best.append((score, p))
    best.sort(key=lambda x: x[0], reverse=True)
    category = None
    for c in db.scalars(select(Category).where(Category.is_active.is_(True))).all():
        kws = [c.name_uz, c.name_ru, c.name_en or "", *(c.keywords or [])]
        if any(normalize_text(k) and all(any(_stem_match(qt, kt) for qt in qtoks) for kt in tokens(k)) for k in kws):
            category = c
            break
    if not best:
        return None, [], category
    top = best[0][0]
    tied = [p for s, p in best if s >= top - 1e-9]
    return best[0][1], [p for _, p in best[1:6]] if len(tied) == 1 else tied[1:6], category


def parse_deterministic(db: Session, q: str) -> Parsed:
    ql = " " + q.lower() + " "
    lang = detect_language(q)
    intent = None
    for name in ("price_increases", "price_decreases", "regions_most_offers", "best_total", "average_price",
                 "compare_regions", "suppliers", "cheapest"):
        if any(k in ql for k in KEYWORDS[name]):
            intent = name
            break
    regions = resolve_regions(db, q)
    product, alts, category = resolve_product(db, q)
    qty = None
    m = _QTY.search(q)
    if m:
        qty = Decimal(re.sub(r"\s", "", m.group(1)).replace(",", "."))
        if intent in (None, "suppliers"):
            intent = "min_quantity"
    elif (m2 := _QTY_ANY.search(q)):
        qty = Decimal(re.sub(r"\s", "", m2.group(1)).replace(",", "."))
    if intent == "compare_regions" and len(regions) < 2 and product is None:
        intent = None
    if intent is None:
        intent = "compare_regions" if len(regions) >= 2 and product else ("product_overview" if product else "unknown")
    pt = "wholesale" if re.search(r"(wholesale|ulgurji|оптов|опт )", q, re.I) else (
        "retail" if re.search(r"(retail|chakana|розни)", q, re.I) else None)
    return Parsed(intent, lang, product, alts, category, regions, qty, pt)


# ---------------------------------------------------------------- tools

def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    d = Decimal(v)
    return f"{d:,.0f}".replace(",", " ") if d >= 100 else f"{d:,.2f}".replace(",", " ")


def run_tool(db: Session, p: Parsed, include_simulated: bool = True) -> dict[str, Any]:
    if p.intent in ("price_increases", "price_decreases"):
        mv = analytics.price_movers(db, category_id=p.category.id if p.category else None,
                                    region_id=p.regions[0].id if p.regions else None, include_simulated=include_simulated)
        return {"tool": "price_movers", "result": mv}
    if p.intent == "regions_most_offers":
        ro = analytics.regional_overview(db, category_id=p.category.id if p.category else None, include_simulated=include_simulated)
        if p.product:
            rp = regional_prices(db, p.product.id, include_simulated)
            return {"tool": "regional_prices", "result": sorted(rp, key=lambda r: -r["offers"])}
        return {"tool": "regional_overview", "result": sorted(ro, key=lambda r: -r["active_offers"])}
    if p.product is None:
        return {"tool": None, "result": None}
    if p.intent == "compare_regions" or (p.intent == "average_price" and len(p.regions) >= 2):
        rp = regional_prices(db, p.product.id, include_simulated)
        if p.regions:
            ids = {r.id for r in p.regions}
            rp = [r for r in rp if r["region_id"] in ids]
        return {"tool": "regional_prices", "result": rp, "requested_regions": [r.code for r in p.regions]}
    params = CompareParams(product_id=p.product.id, quantity=p.quantity if p.intent in ("best_total", "min_quantity") else None,
                           region_id=p.regions[0].id if p.regions and p.intent != "best_total" else None,
                           buyer_region_id=p.regions[0].id if p.regions else None, price_type=p.price_type,
                           include_simulated=include_simulated)
    res = compare_offers(db, params)
    if p.intent == "min_quantity" and p.quantity:
        for o in res["offers"]:
            ab = o["available_base_units"]
            o["meets_quantity"] = ab is not None and Decimal(ab) >= p.quantity
    return {"tool": "compare_offers", "result": res}


def _sources_from(tool: dict) -> list[dict]:
    if tool.get("tool") == "compare_offers":
        srcs: dict[str, dict] = {}
        for o in tool["result"]["offers"]:
            s = o["provenance"]
            key = s["source"]
            e = srcs.setdefault(key, {"name": key, "kind": s["kind"], "is_simulated": s["is_simulated"], "latest": None, "offers": 0})
            e["offers"] += 1
            ts = o["freshness"]["price_updated_at"]
            if e["latest"] is None or (ts and ts > e["latest"]):
                e["latest"] = ts
        return list(srcs.values())
    return [{"name": "TradeFlow price observations & offers", "kind": "aggregated", "is_simulated": None}]


T = {
    "no_product": {"en": "I couldn't identify a product in your question. Try naming it as in the catalog (e.g. \"Portland cement M400 50kg\").",
                   "ru": "Не удалось определить товар в вопросе. Укажите название как в каталоге (например, «Портландцемент М400 50 кг»).",
                   "uz": "Savolingizdagi mahsulotni aniqlay olmadim. Katalogdagi nomini yozing (masalan, \"Portlandsement M400 50 kg\")."},
    "no_offers": {"en": "There are no active comparable offers for {p}{r} on TradeFlow right now.",
                  "ru": "Сейчас на TradeFlow нет активных сопоставимых предложений по «{p}»{r}.",
                  "uz": "Hozir TradeFlow'da {p}{r} bo'yicha faol taqqoslanadigan takliflar yo'q."},
    "unknown": {"en": "I can answer questions about prices, suppliers, regional comparisons, price changes and offer availability using TradeFlow data. I couldn't map this question to one of those.",
                "ru": "Я отвечаю на вопросы о ценах, поставщиках, сравнении регионов, изменении цен и наличии предложений по данным TradeFlow. Этот вопрос я не смог сопоставить ни с одним из них.",
                "uz": "Men TradeFlow ma'lumotlari asosida narxlar, yetkazib beruvchilar, hududlar taqqoslash, narx o'zgarishlari va takliflar haqidagi savollarga javob beraman. Bu savolni ulardan biriga bog'lay olmadim."},
}


def compose_deterministic(p: Parsed, tool: dict) -> str:
    L = p.language
    pname = p.product.name if p.product else ""
    rtxt = (f" ({', '.join(getattr(r, 'name_' + ('ru' if L == 'ru' else 'uz' if L == 'uz' else 'en')) for r in p.regions)})"
            if p.regions else "")
    t, res = tool.get("tool"), tool.get("result")
    if t is None:
        return T["no_product"][L] if p.intent != "unknown" else T["unknown"][L]

    if t == "price_movers":
        rows = res.get("increases" if p.intent == "price_increases" else "decreases", [])
        if res.get("status") != "ok" or not rows:
            return {"en": "Insufficient data: no products crossed the ±{th}% change threshold over the last {w} days.",
                    "ru": "Недостаточно данных: ни один товар не превысил порог изменения ±{th}% за последние {w} дн.",
                    "uz": "Ma'lumot yetarli emas: so'nggi {w} kunda hech bir mahsulot ±{th}% chegarasidan o'tmagan."}[L].format(
                th=res.get("threshold_pct"), w=res.get("window_days"))
        head = {"en": "Largest {d} (last {w} days vs previous {w}):", "ru": "Наибольшее {d} цен (последние {w} дн. против предыдущих {w}):",
                "uz": "Eng katta narx {d} (so'nggi {w} kun va oldingi {w} kun):"}[L].format(
            d={"en": ("increases" if p.intent == "price_increases" else "decreases"),
               "ru": ("повышение" if p.intent == "price_increases" else "снижение"),
               "uz": ("o'sishi" if p.intent == "price_increases" else "pasayishi")}[L], w=res["window_days"])
        lines = [f"• {r['name']}: {r['change_pct']:+.1f}% ({_fmt(r['prev_avg'])} → {_fmt(r['current_avg'])} UZS/{r['base_unit']})" for r in rows[:7]]
        return "\n".join([head, *lines])

    if t in ("regional_overview", "regional_prices") and p.intent == "regions_most_offers":
        rows = [r for r in res if (r.get("active_offers") or r.get("offers"))][:7]
        if not rows:
            return T["no_offers"][L].format(p=pname or "—", r="")
        head = {"en": "Regions by number of active offers:", "ru": "Регионы по количеству активных предложений:",
                "uz": "Faol takliflar soni bo'yicha hududlar:"}[L]
        nm = "name_ru" if L == "ru" else "name_uz"
        return "\n".join([head] + [f"• {r[nm]}: {r.get('active_offers', r.get('offers'))}" for r in rows])

    if t == "regional_prices":
        if not res:
            return T["no_offers"][L].format(p=pname, r=rtxt)
        nm = "name_ru" if L == "ru" else "name_uz"
        unit = p.product.base_unit.code
        head = {"en": f"{pname} — price per {unit} by region (active offers):",
                "ru": f"{pname} — цена за {unit} по регионам (активные предложения):",
                "uz": f"{pname} — hududlar bo'yicha {unit} narxi (faol takliflar):"}[L]
        lines = [f"• {r[nm]}: avg {_fmt(r['avg'])}, min {_fmt(r['min'])}, max {_fmt(r['max'])} UZS ({r['offers']})" for r in res]
        missing = [r for r in p.regions if r.id not in {x['region_id'] for x in res}]
        if missing:
            lines.append({"en": "No offers in: ", "ru": "Нет предложений в: ", "uz": "Taklif yo'q: "}[L] + ", ".join(getattr(r, nm) for r in missing))
        if len(res) >= 2:
            lo, hi = res[0], res[-1]
            diff = (Decimal(hi["avg"]) - Decimal(lo["avg"])) / Decimal(lo["avg"]) * 100
            lines.append({"en": f"{hi[nm]} is {diff:.1f}% above {lo[nm]} on average.",
                          "ru": f"В среднем {hi[nm]} на {diff:.1f}% дороже, чем {lo[nm]}.",
                          "uz": f"O'rtacha {hi[nm]} {lo[nm]}dan {diff:.1f}% qimmat."}[L])
        return "\n".join([head, *lines])

    # compare_offers
    offers = [o for o in res["offers"] if o["excluded_reason"] is None]
    if not offers:
        return T["no_offers"][L].format(p=pname, r=rtxt)
    s = res["summary"]
    unit = s["base_unit"]
    by_id = {o["offer_id"]: o for o in res["offers"]}
    cheapest = by_id.get(res["cheapest_offer_id"])
    best = by_id.get(res["best_offer_id"])
    lines: list[str] = []
    if p.intent == "average_price":
        lines.append({"en": f"Average listed price for {pname}{rtxt}: {_fmt(s['avg_per_base_unit_uzs'])} UZS/{unit} across {s['offers_comparable']} active offers (range {_fmt(s['min_per_base_unit_uzs'])}–{_fmt(s['max_per_base_unit_uzs'])}).",
                      "ru": f"Средняя цена предложений на «{pname}»{rtxt}: {_fmt(s['avg_per_base_unit_uzs'])} сум/{unit} по {s['offers_comparable']} активным предложениям (диапазон {_fmt(s['min_per_base_unit_uzs'])}–{_fmt(s['max_per_base_unit_uzs'])}).",
                      "uz": f"{pname}{rtxt} uchun o'rtacha taklif narxi: {_fmt(s['avg_per_base_unit_uzs'])} so'm/{unit}, {s['offers_comparable']} ta faol taklif (oraliq {_fmt(s['min_per_base_unit_uzs'])}–{_fmt(s['max_per_base_unit_uzs'])})."}[L])
    elif p.intent in ("suppliers", "min_quantity"):
        rows = offers
        if p.intent == "min_quantity" and p.quantity:
            rows = [o for o in offers if o.get("meets_quantity")]
            lines.append({"en": f"Suppliers of {pname}{rtxt} declaring stock for at least {_fmt(p.quantity)} {unit}: {len(rows)}",
                          "ru": f"Поставщики «{pname}»{rtxt}, заявившие запас не менее {_fmt(p.quantity)} {unit}: {len(rows)}",
                          "uz": f"{pname}{rtxt} bo'yicha kamida {_fmt(p.quantity)} {unit} zaxirasi bor yetkazib beruvchilar: {len(rows)}"}[L])
        else:
            lines.append({"en": f"Suppliers offering {pname}{rtxt}: {len(rows)}", "ru": f"Поставщики «{pname}»{rtxt}: {len(rows)}",
                          "uz": f"{pname}{rtxt} yetkazib beruvchilari: {len(rows)}"}[L])
        for o in sorted(rows, key=lambda o: Decimal(o["price"]["per_base_unit_uzs"]))[:8]:
            lines.append(f"• {o['supplier']['name']} — {o['region']['name_ru' if L == 'ru' else 'name_uz']}, "
                         f"{_fmt(o['price']['per_base_unit_uzs'])} UZS/{unit}, MOQ {_fmt(o['moq'])}, "
                         f"stock {_fmt(o['available_qty'])} {o['price']['unit']} [{o['supplier']['verification_status']}]")
    else:
        if cheapest:
            lines.append({"en": f"Cheapest {pname}{rtxt}: {cheapest['supplier']['name']} ({cheapest['region']['name_uz']}) — {_fmt(cheapest['price']['per_base_unit_uzs'])} UZS/{unit} ({cheapest['price']['price_type']}).",
                          "ru": f"Самое дешёвое предложение «{pname}»{rtxt}: {cheapest['supplier']['name']} ({cheapest['region']['name_ru']}) — {_fmt(cheapest['price']['per_base_unit_uzs'])} сум/{unit}.",
                          "uz": f"Eng arzon {pname}{rtxt}: {cheapest['supplier']['name']} ({cheapest['region']['name_uz']}) — {_fmt(cheapest['price']['per_base_unit_uzs'])} so'm/{unit}."}[L])
            if p.quantity and cheapest["cost"]["total_uzs"] is not None:
                lines.append({"en": f"Total for {_fmt(p.quantity)} {unit}: {_fmt(cheapest['cost']['total_uzs'])} UZS.",
                              "ru": f"Итого за {_fmt(p.quantity)} {unit}: {_fmt(cheapest['cost']['total_uzs'])} сум.",
                              "uz": f"{_fmt(p.quantity)} {unit} uchun jami: {_fmt(cheapest['cost']['total_uzs'])} so'm."}[L])
        if best:
            top = sorted(best["score_breakdown"], key=lambda b: -b["contribution"])[:3]
            why = ", ".join(f"{b['criterion']} {b['score']:.2f}" for b in top)
            lines.append({"en": f"Best overall: {best['supplier']['name']} (score {best['score']:.2f}; {why})" + (f", total {_fmt(best['cost']['total_uzs'])} UZS" if best['cost']['total_uzs'] is not None else "") + ".",
                          "ru": f"Лучшее в целом: {best['supplier']['name']} (оценка {best['score']:.2f}; {why})" + (f", итого {_fmt(best['cost']['total_uzs'])} сум" if best['cost']['total_uzs'] is not None else "") + ".",
                          "uz": f"Umumiy eng maqbul: {best['supplier']['name']} (ball {best['score']:.2f}; {why})" + (f", jami {_fmt(best['cost']['total_uzs'])} so'm" if best['cost']['total_uzs'] is not None else "") + "."}[L])
        lines.append({"en": f"Based on {s['offers_comparable']} active offers; range {_fmt(s['min_per_base_unit_uzs'])}–{_fmt(s['max_per_base_unit_uzs'])} UZS/{unit}.",
                      "ru": f"На основе {s['offers_comparable']} активных предложений; диапазон {_fmt(s['min_per_base_unit_uzs'])}–{_fmt(s['max_per_base_unit_uzs'])} сум/{unit}.",
                      "uz": f"{s['offers_comparable']} ta faol taklif asosida; oraliq {_fmt(s['min_per_base_unit_uzs'])}–{_fmt(s['max_per_base_unit_uzs'])} so'm/{unit}."}[L])
    return "\n".join(lines)


def _disclaimers(p: Parsed, tool: dict) -> list[str]:
    out = {"en": ["Prices are supplier-declared or listed asking prices unless marked as verified transactions."],
           "ru": ["Цены — заявленные поставщиками или опубликованные цены предложений, если не отмечены как подтверждённые сделки."],
           "uz": ["Narxlar, tasdiqlangan bitim deb belgilanmagan bo'lsa, yetkazib beruvchi e'lon qilgan yoki taklif narxlaridir."]}[p.language]
    sim = False
    r = tool.get("result")
    if tool.get("tool") == "compare_offers" and r:
        sim = r["summary"]["simulated_offers"] > 0
    elif tool.get("tool") in ("regional_prices", "regional_overview", "price_movers"):
        sim = True  # aggregated sets may include simulated demo records; UI shows the toggle
    if sim:
        out.append({"en": "Includes SIMULATED demo data — not real market information.",
                    "ru": "Включает СИМУЛИРОВАННЫЕ демо-данные — это не реальная рыночная информация.",
                    "uz": "SIMULYATSIYA qilingan demo ma'lumotlar mavjud — bu haqiqiy bozor ma'lumoti emas."}[p.language])
    return out


LLM_PARSE_SYSTEM = (
    "You convert a user's question about the Uzbekistan B2B market into a JSON tool call. "
    f"intent must be one of {list(INTENTS)} or 'unknown'. Fields: intent, product_query (string or null, the product as "
    "named by the user), regions (list of region names as written), quantity (number or null), price_type "
    "('wholesale'|'retail'|null), language ('uz'|'ru'|'en'). Never invent values not present in the question."
)
LLM_ANSWER_SYSTEM = (
    "You are TradeFlow's market assistant. Answer ONLY from the JSON tool result provided. Do not invent suppliers, "
    "prices, stock, statistics or trends. Quote numbers exactly as given (UZS). If the result is empty or says "
    "insufficient_data, say so plainly. Mention when data is simulated. Keep it concise, in the requested language."
)


def answer(db: Session, question: str, include_simulated: bool = True, language: str | None = None) -> dict[str, Any]:
    question = question.strip()[:1000]
    parsed = parse_deterministic(db, question)
    if language in ("uz", "ru", "en"):
        parsed.language = language
    mode, llm_note = "deterministic", None
    provider = get_provider()
    if provider:
        try:
            j = provider.complete_json(LLM_PARSE_SYSTEM, question)
            if j.get("intent") in INTENTS:
                parsed.intent = j["intent"]
            if j.get("product_query"):
                prod, alts, _ = resolve_product(db, str(j["product_query"]))
                if prod:
                    parsed.product, parsed.product_alternatives = prod, alts
            if j.get("regions"):
                regs = resolve_regions(db, " ".join(map(str, j["regions"])))
                if regs:
                    parsed.regions = regs
            if j.get("quantity") not in (None, ""):
                parsed.quantity = Decimal(str(j["quantity"]))
            if j.get("price_type") in ("wholesale", "retail"):
                parsed.price_type = j["price_type"]
            mode = "llm"
        except Exception as e:  # noqa: BLE001 — fall back, but report it
            llm_note = f"LLM unavailable ({type(e).__name__}); used deterministic engine."

    tool = run_tool(db, parsed, include_simulated)
    text = compose_deterministic(parsed, tool)
    if mode == "llm" and tool.get("result") is not None:
        try:
            payload = json.dumps({"question": question, "language": parsed.language, "intent": parsed.intent,
                                  "tool": tool["tool"], "result": tool["result"], "draft_answer": text}, default=str)[:60000]
            text = provider.complete_text(LLM_ANSWER_SYSTEM, payload)
        except Exception as e:  # noqa: BLE001
            llm_note = f"LLM phrasing failed ({type(e).__name__}); showing deterministic answer."

    data = tool.get("result")
    return {
        "question": question,
        "answer": text,
        "mode": mode,
        "note": llm_note,
        "language": parsed.language,
        "intent": parsed.intent,
        "entities": {
            "product": {"id": parsed.product.id, "name": parsed.product.name} if parsed.product else None,
            "alternatives": [{"id": a.id, "name": a.name} for a in parsed.product_alternatives],
            "category": {"id": parsed.category.id, "slug": parsed.category.slug} if parsed.category else None,
            "regions": [{"id": r.id, "code": r.code, "name_uz": r.name_uz, "name_ru": r.name_ru} for r in parsed.regions],
            "quantity": parsed.quantity,
            "price_type": parsed.price_type,
        },
        "tool": tool.get("tool"),
        "data": data,
        "sources": _sources_from(tool) if data is not None else [],
        "disclaimers": _disclaimers(parsed, tool),
    }


__all__ = ["answer"]
