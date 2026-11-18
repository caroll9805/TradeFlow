"""Deterministic market statistics, anomaly detection and (guarded) forecasting.

Everything returned here is computed from stored observations/offers. Forecasts are labelled
'estimate' and only produced when enough history exists."""
from datetime import timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    DataSource,
    Offer,
    PriceObservation,
    Product,
    QuoteRequest,
    Region,
    SearchEvent,
    Supplier,
)
from app.models.base import utcnow
from app.services.geo import aware
from app.services.settings_service import get_setting

INSUFFICIENT = "insufficient_data"


def _obs_frame(db: Session, *, product_id: int | None = None, region_id: int | None = None,
               category_id: int | None = None, since=None, include_simulated: bool = True,
               price_type: str | None = None) -> pd.DataFrame:
    q = select(PriceObservation.id, PriceObservation.product_id, PriceObservation.region_id,
               PriceObservation.supplier_id, PriceObservation.observed_at, PriceObservation.normalized_price_uzs,
               PriceObservation.provenance_kind, PriceObservation.is_simulated, PriceObservation.data_source_id,
               PriceObservation.price_type).where(PriceObservation.normalized_price_uzs.is_not(None))
    if product_id:
        q = q.where(PriceObservation.product_id == product_id)
    if region_id:
        q = q.where(PriceObservation.region_id == region_id)
    if category_id:
        q = q.join(Product, Product.id == PriceObservation.product_id).where(Product.category_id == category_id)
    if since is not None:
        q = q.where(PriceObservation.observed_at >= since)
    if not include_simulated:
        q = q.where(PriceObservation.is_simulated.is_(False))
    if price_type:
        q = q.where(PriceObservation.price_type == price_type)
    rows = db.execute(q).all()
    df = pd.DataFrame(rows, columns=["id", "product_id", "region_id", "supplier_id", "observed_at", "price",
                                     "provenance", "is_simulated", "source_id", "price_type"])
    if not df.empty:
        df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
        df["price"] = df["price"].astype(float)
    return df


def overview(db: Session, include_simulated: bool = True, category_id: int | None = None,
             region_id: int | None = None) -> dict:
    def flt(q, model):
        if not include_simulated and hasattr(model, "is_simulated"):
            q = q.where(model.is_simulated.is_(False))
        return q

    pq = flt(select(func.count(Product.id)).where(Product.status == "active"), Product)
    if category_id:
        pq = pq.where(Product.category_id == category_id)
    sq = flt(select(func.count(Supplier.id)).where(Supplier.is_active.is_(True)), Supplier)
    if region_id:
        sq = sq.where(Supplier.region_id == region_id)
    oq = flt(select(func.count(Offer.id)).where(Offer.is_active.is_(True)), Offer)
    if region_id:
        oq = oq.where(Offer.region_id == region_id)
    if category_id:
        oq = oq.join(Product, Product.id == Offer.product_id).where(Product.category_id == category_id)
    vq = flt(select(func.count(Supplier.id)).where(Supplier.verification_status == "verified"), Supplier)
    obs_q = flt(select(func.count(PriceObservation.id), func.max(PriceObservation.collected_at)), PriceObservation)

    obs_count, last_collected = db.execute(obs_q).one()
    sim_offers = db.scalar(select(func.count(Offer.id)).where(Offer.is_active.is_(True), Offer.is_simulated.is_(True)))
    by_cat = db.execute(
        flt(select(Category.id, Category.slug, Category.name_uz, Category.name_ru, func.count(Offer.id))
            .join(Product, Product.category_id == Category.id)
            .join(Offer, (Offer.product_id == Product.id) & (Offer.is_active.is_(True)), isouter=True)
            .group_by(Category.id).order_by(Category.sort_order), Offer)
    ).all()
    return {
        "products_indexed": db.scalar(pq),
        "suppliers_registered": db.scalar(sq),
        "suppliers_verified": db.scalar(vq),
        "active_offers": db.scalar(oq),
        "simulated_active_offers": sim_offers,
        "price_observations": obs_count,
        "last_collected_at": last_collected,
        "offers_by_category": [{"category_id": c[0], "slug": c[1], "name_uz": c[2], "name_ru": c[3], "offers": c[4]}
                               for c in by_cat],
    }


def price_history(db: Session, product_id: int, *, granularity: str = "week", region_id: int | None = None,
                  days: int = 180, include_simulated: bool = True, price_type: str | None = None) -> dict:
    since = utcnow() - timedelta(days=days)
    df = _obs_frame(db, product_id=product_id, region_id=region_id, since=since,
                    include_simulated=include_simulated, price_type=price_type)
    product = db.get(Product, product_id)
    if df.empty:
        return {"status": INSUFFICIENT, "points": [], "base_unit": product.base_unit.code if product else None}
    freq = {"day": "D", "week": "W-MON", "month": "MS"}[granularity]
    g = df.set_index("observed_at").groupby(pd.Grouper(freq=freq))["price"]
    agg = pd.DataFrame({"avg": g.mean(), "min": g.min(), "max": g.max(), "count": g.count()}).dropna()
    points = [{"period": idx.isoformat(), "avg": round(r["avg"], 2), "min": round(r["min"], 2),
               "max": round(r["max"], 2), "observations": int(r["count"])} for idx, r in agg.iterrows()]
    change = None
    if len(points) >= 2 and points[0]["avg"]:
        change = round((points[-1]["avg"] - points[0]["avg"]) / points[0]["avg"] * 100, 2)
    provenance = {str(k): int(v) for k, v in df.groupby("provenance").size().items()}
    return {"status": "ok", "granularity": granularity, "base_unit": product.base_unit.code, "points": points,
            "change_pct": change, "observations": int(len(df)), "provenance_breakdown": provenance,
            "simulated_share": round(float(df["is_simulated"].mean()), 3),
            "first_observed_at": df["observed_at"].min().isoformat(), "last_observed_at": df["observed_at"].max().isoformat()}


def price_movers(db: Session, *, category_id: int | None = None, region_id: int | None = None,
                 include_simulated: bool = True, limit: int = 10) -> dict:
    window = int(get_setting(db, "analytics.mover_window_days"))
    thr = float(get_setting(db, "analytics.mover_threshold_pct"))
    now = utcnow()
    df = _obs_frame(db, region_id=region_id, category_id=category_id, since=now - timedelta(days=2 * window),
                    include_simulated=include_simulated)
    if df.empty:
        return {"status": INSUFFICIENT, "increases": [], "decreases": [], "window_days": window, "threshold_pct": thr}
    cut = pd.Timestamp(now - timedelta(days=window))
    cur = df[df["observed_at"] >= cut].groupby("product_id")["price"].agg(["mean", "count"])
    prev = df[df["observed_at"] < cut].groupby("product_id")["price"].agg(["mean", "count"])
    j = cur.join(prev, lsuffix="_cur", rsuffix="_prev", how="inner")
    j = j[(j["count_cur"] >= 2) & (j["count_prev"] >= 2)]
    j["change_pct"] = (j["mean_cur"] - j["mean_prev"]) / j["mean_prev"] * 100
    names = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(j.index.tolist()))).all()} if len(j) else {}

    def rows(sub):
        return [{"product_id": int(pid), "name": names[pid].name, "base_unit": names[pid].base_unit.code,
                 "category_id": names[pid].category_id,
                 "prev_avg": round(r["mean_prev"], 2), "current_avg": round(r["mean_cur"], 2),
                 "change_pct": round(r["change_pct"], 2), "observations": int(r["count_cur"] + r["count_prev"])}
                for pid, r in sub.iterrows()]

    inc = j[j["change_pct"] >= thr].sort_values("change_pct", ascending=False).head(limit)
    dec_ = j[j["change_pct"] <= -thr].sort_values("change_pct").head(limit)
    return {"status": "ok", "window_days": window, "threshold_pct": thr, "increases": rows(inc), "decreases": rows(dec_),
            "method": f"Average normalized price over the last {window} days vs the previous {window} days; "
                      "products need ≥2 observations in each window."}


def regional_overview(db: Session, *, category_id: int | None = None, include_simulated: bool = True) -> list[dict]:
    cond = (Offer.region_id == Region.id) & (Offer.is_active.is_(True))
    if category_id:
        cond = cond & Offer.product_id.in_(select(Product.id).where(Product.category_id == category_id))
    if not include_simulated:
        cond = cond & Offer.is_simulated.is_(False)
    q = (select(Region.id, Region.code, Region.name_uz, Region.name_ru, Region.name_en, Region.center_lat, Region.center_lng,
                func.count(func.distinct(Offer.id)), func.count(func.distinct(Offer.supplier_id)))
         .select_from(Region).join(Offer, cond, isouter=True))
    rows = db.execute(q.group_by(Region.id).order_by(Region.sort_order)).all()
    sup = dict(db.execute(select(Supplier.region_id, func.count(Supplier.id)).where(Supplier.is_active.is_(True))
                          .group_by(Supplier.region_id)).all())
    return [{"region_id": r[0], "code": r[1], "name_uz": r[2], "name_ru": r[3], "name_en": r[4],
             "center_lat": r[5], "center_lng": r[6], "active_offers": r[7], "suppliers_with_offers": r[8],
             "suppliers_registered": sup.get(r[0], 0)} for r in rows]


def supply_demand(db: Session, product_id: int, days: int = 30) -> dict:
    """Separate indicators — search interest is NOT demand."""
    since = utcnow() - timedelta(days=days)
    offers = db.scalars(select(Offer).where(Offer.product_id == product_id, Offer.is_active.is_(True))).unique().all()
    declared = [Decimal(o.available_qty) * Decimal(o.units_per_offer_unit) for o in offers
                if o.available_qty is not None and o.units_per_offer_unit]
    searches = db.scalar(select(func.count(SearchEvent.id)).where(SearchEvent.product_id == product_id,
                                                                  SearchEvent.created_at >= since))
    quotes = db.scalar(select(func.count(QuoteRequest.id)).where(QuoteRequest.product_id == product_id,
                                                                 QuoteRequest.created_at >= since))
    tx = db.scalar(select(func.count(PriceObservation.id)).where(PriceObservation.product_id == product_id,
                                                                 PriceObservation.provenance_kind == "verified_transaction",
                                                                 PriceObservation.observed_at >= since))
    return {
        "window_days": days,
        "observed_supply": {"active_offers": len(offers), "active_suppliers": len({o.supplier_id for o in offers}),
                            "regions": len({o.region_id for o in offers})},
        "declared_stock_base_units": sum(declared) if declared else INSUFFICIENT,
        "declared_stock_offers_reporting": len(declared),
        "search_interest": searches,
        "quote_requests": quotes,
        "completed_transactions": tx if tx else INSUFFICIENT,
        "estimated_demand": INSUFFICIENT,
        "note": "Search interest (searches and product page views on TradeFlow) and quote requests are platform activity signals, not measured market demand.",
    }


def detect_anomalies(db: Session, *, product_id: int | None = None, category_id: int | None = None,
                     days: int = 90, include_simulated: bool = True, limit: int = 50) -> dict:
    """Robust z-score (median/MAD) per product; IsolationForest added when a product has enough history."""
    zthr = float(get_setting(db, "analytics.anomaly_z_threshold"))
    min_if = int(get_setting(db, "analytics.min_points_for_isolation_forest"))
    df = _obs_frame(db, product_id=product_id, category_id=category_id, since=utcnow() - timedelta(days=days),
                    include_simulated=include_simulated)
    if df.empty:
        return {"status": INSUFFICIENT, "anomalies": []}
    out = []
    for pid, g in df.groupby("product_id"):
        if len(g) < 5:
            continue
        med = g["price"].median()
        mad = (g["price"] - med).abs().median()
        if mad == 0:
            continue
        z = 0.6745 * (g["price"] - med) / mad
        iso_flags = pd.Series(False, index=g.index)
        if len(g) >= min_if:
            from sklearn.ensemble import IsolationForest

            days = (g["observed_at"] - g["observed_at"].min()).dt.total_seconds() / 86400.0
            X = np.column_stack([np.log(g["price"].clip(lower=1e-9)), days])
            iso = IsolationForest(contamination="auto", random_state=0).fit(X)
            iso_flags = pd.Series(iso.predict(X) == -1, index=g.index)
        flagged = g[(z.abs() >= zthr)]
        for idx, r in flagged.iterrows():
            out.append({"observation_id": int(r["id"]), "product_id": int(pid), "region_id": int(r["region_id"]),
                        "supplier_id": None if pd.isna(r["supplier_id"]) else int(r["supplier_id"]),
                        "observed_at": r["observed_at"].isoformat(), "price": round(r["price"], 2),
                        "median": round(med, 2), "robust_z": round(float(z[idx]), 2),
                        "isolation_forest_flag": bool(iso_flags[idx]),
                        "direction": "above" if r["price"] > med else "below", "is_simulated": bool(r["is_simulated"])})
    out.sort(key=lambda a: abs(a["robust_z"]), reverse=True)
    names = {p.id: p.name for p in db.scalars(select(Product).where(Product.id.in_({a["product_id"] for a in out}))).all()} if out else {}
    for a in out:
        a["product_name"] = names.get(a["product_id"])
    return {"status": "ok", "method": f"Robust z-score |z| ≥ {zthr} (median/MAD) per product over {days} days; "
                                      f"IsolationForest cross-check when ≥{min_if} observations.",
            "anomalies": out[:limit]}


def forecast(db: Session, product_id: int, horizon_weeks: int = 4, region_id: int | None = None) -> dict:
    """Linear trend on weekly averages. Only when enough real history exists. Always labelled an estimate."""
    min_pts = int(get_setting(db, "analytics.min_points_for_forecast"))
    hist = price_history(db, product_id, granularity="week", region_id=region_id, days=365)
    pts = hist["points"]
    if len(pts) < min_pts:
        return {"status": INSUFFICIENT, "required_weeks": min_pts, "available_weeks": len(pts), "kind": "estimate"}
    from sklearn.linear_model import LinearRegression

    y = np.array([p["avg"] for p in pts])
    X = np.arange(len(y)).reshape(-1, 1)
    model = LinearRegression().fit(X, y)
    resid = y - model.predict(X)
    sigma = float(np.std(resid, ddof=1)) if len(y) > 2 else 0.0
    last = pd.Timestamp(pts[-1]["period"])
    fc = []
    for h in range(1, horizon_weeks + 1):
        val = float(model.predict(np.array([[len(y) - 1 + h]]))[0])
        fc.append({"period": (last + pd.Timedelta(weeks=h)).isoformat(), "estimate": round(val, 2),
                   "low": round(val - 1.96 * sigma, 2), "high": round(val + 1.96 * sigma, 2)})
    return {"status": "ok", "kind": "estimate", "method": "Linear trend on weekly averages (scikit-learn), ±1.96σ band",
            "simulated_share": hist.get("simulated_share"), "base_unit": hist["base_unit"], "forecast": fc,
            "disclaimer": "Statistical estimate, not an observed market price."}


def source_freshness(db: Session) -> list[dict]:
    rows = db.execute(select(DataSource, func.max(PriceObservation.collected_at), func.count(PriceObservation.id))
                      .join(PriceObservation, PriceObservation.data_source_id == DataSource.id, isouter=True)
                      .group_by(DataSource.id)).all()
    now = utcnow()
    out = []
    for ds, last, n in rows:
        last = aware(last)
        age = (now - last).total_seconds() / 3600 if last else None
        out.append({"source_id": ds.id, "code": ds.code, "name": ds.name, "source_type": ds.source_type,
                    "provenance": ds.default_provenance, "is_simulated": ds.is_simulated,
                    "reliability_score": ds.reliability_score, "freshness_hours": ds.freshness_hours,
                    "last_collected_at": last, "observations": n,
                    "status": "no_data" if last is None else ("fresh" if age <= ds.freshness_hours else "stale")})
    return out
