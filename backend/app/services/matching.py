"""Product matching across supplier naming conventions.

Order of evidence: barcode (exact) > SKU (exact) > normalized-name exact > fuzzy similarity
combined with brand/category/unit agreement. Results carry a confidence score and reasons;
uncertain matches go to human review and are never merged automatically."""
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Product
from app.services.text import normalize_text, tokens


@dataclass
class MatchCandidate:
    product: Product
    score: float
    method: str
    reasons: list[str] = field(default_factory=list)


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    jacc = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    return 0.5 * jacc + 0.5 * seq


def find_matches(
    db: Session,
    name: str,
    *,
    barcode: str | None = None,
    sku: str | None = None,
    brand: str | None = None,
    category_id: int | None = None,
    limit: int = 5,
) -> list[MatchCandidate]:
    if barcode:
        p = db.scalar(select(Product).where(Product.barcode == barcode.strip()))
        if p:
            return [MatchCandidate(p, 1.0, "barcode", ["Exact barcode match"])]
    if sku:
        p = db.scalar(select(Product).where(Product.sku == sku.strip()))
        if p:
            return [MatchCandidate(p, 0.98, "sku", ["Exact SKU match"])]

    norm = normalize_text(name)
    if not norm:
        return []
    exact = db.scalars(select(Product).where(Product.normalized_name == norm)).all()
    if len(exact) == 1:
        return [MatchCandidate(exact[0], 0.97, "normalized_name", ["Exact normalized name match"])]

    # Candidate pre-filter: any shared token in name (cheap LIKE filter), optionally same category.
    toks = [t for t in tokens(name) if len(t) >= 3][:6]
    q = select(Product).where(Product.status != "archived")
    if toks:
        q = q.where(or_(*[Product.normalized_name.contains(t) for t in toks]))
    if category_id:
        q = q.where(Product.category_id == category_id)
    candidates = db.scalars(q.limit(300)).all()

    results: list[MatchCandidate] = []
    nbrand = normalize_text(brand) if brand else ""
    for p in candidates:
        names = [p.normalized_name] + [normalize_text(t) for t in (p.search_terms or [])]
        sim = max(_similarity(norm, n) for n in names)
        reasons = [f"Name similarity {sim:.2f}"]
        score = sim
        if nbrand and p.brand:
            if normalize_text(p.brand) == nbrand:
                score = min(1.0, score + 0.08)
                reasons.append("Brand matches")
            else:
                score -= 0.25
                reasons.append("Brand differs")
        if category_id and p.category_id == category_id:
            reasons.append("Same category")
        results.append(MatchCandidate(p, round(max(score, 0.0), 3), "fuzzy", reasons))
    results.sort(key=lambda c: c.score, reverse=True)
    return results[:limit]
