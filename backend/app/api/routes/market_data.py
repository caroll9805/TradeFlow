"""Market Data Engine administration: sources, connectors, jobs, imports, matching review, observations."""
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import PageParams, get_or_404, observation_out, paginate, product_out
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require
from app.models import (
    CollectionJob,
    CollectionLog,
    DataConnector,
    DataSource,
    PriceObservation,
    Product,
    ProductMatch,
    Region,
    Supplier,
    Unit,
    User,
    VerificationRequest,
)
from app.models.base import utcnow
from app.schemas import DataConnectorIn, DataSourceIn, MatchDecision, ObservationIn
from app.services.audit import audit
from app.services.currency import MissingExchangeRate
from app.services.market_data.base import ConnectorError, get_connector_class
from app.services.market_data.pipeline import RowError, ingest_record, run_collection
from app.services.pricing import record_observation

router = APIRouter(prefix="/market-data", tags=["market-data"])
MD = Depends(require("market_data.manage"))


def source_out(s: DataSource) -> dict:
    return {c: getattr(s, c) for c in ("id", "code", "name", "source_type", "default_provenance", "base_url", "terms_status",
                                       "has_public_api", "requires_auth", "redistribution_allowed", "price_kind",
                                       "review_notes", "reliability_score", "freshness_hours", "is_active",
                                       "is_simulated", "created_at", "updated_at")}


def connector_out(c: DataConnector) -> dict:
    return {"id": c.id, "data_source_id": c.data_source_id, "data_source": c.data_source.name, "name": c.name,
            "connector_type": c.connector_type, "config": c.config, "interval_minutes": c.interval_minutes,
            "is_enabled": c.is_enabled, "last_run_at": c.last_run_at, "last_success_at": c.last_success_at,
            "last_failure_at": c.last_failure_at, "last_error": c.last_error,
            "records_collected_total": c.records_collected_total, "records_rejected_total": c.records_rejected_total,
            "status": "disabled" if not c.is_enabled else ("error" if c.last_error else ("ok" if c.last_success_at else "never_run"))}


def job_out(j: CollectionJob) -> dict:
    return {c: getattr(j, c) for c in ("id", "connector_id", "data_source_id", "trigger", "status", "started_at",
                                       "finished_at", "records_seen", "records_collected", "records_rejected",
                                       "records_pending_review", "records_duplicate", "error", "file_name")} | {
        "data_source": j.data_source.name}


# ---------- sources
@router.get("/sources", dependencies=[MD])
def list_sources(db: Session = Depends(get_db)):
    return [source_out(s) for s in db.scalars(select(DataSource).order_by(DataSource.id)).all()]


@router.post("/sources", status_code=201)
def create_source(body: DataSourceIn, user: User = MD, db: Session = Depends(get_db)):
    if db.scalar(select(DataSource).where(DataSource.code == body.code)):
        raise HTTPException(409, "Code already exists")
    s = DataSource(**body.model_dump(exclude={"base_url"}), base_url=str(body.base_url) if body.base_url else None,
                   is_simulated=body.source_type == "simulated")
    db.add(s)
    db.flush()
    audit(db, user, "create", "data_source", s.id, {"code": s.code})
    db.commit()
    return source_out(s)


@router.put("/sources/{source_id}")
def update_source(source_id: int, body: DataSourceIn, user: User = MD, db: Session = Depends(get_db)):
    s = get_or_404(db, DataSource, source_id, "Data source")
    before = {"terms_status": s.terms_status, "is_active": s.is_active}
    for k, v in body.model_dump(exclude={"base_url"}).items():
        setattr(s, k, v)
    s.base_url = str(body.base_url) if body.base_url else None
    audit(db, user, "update", "data_source", s.id, {"before": before, "after": {"terms_status": s.terms_status, "is_active": s.is_active}})
    db.commit()
    return source_out(s)


# ---------- connectors
@router.get("/connectors", dependencies=[MD])
def list_connectors(db: Session = Depends(get_db)):
    return [connector_out(c) for c in db.scalars(select(DataConnector).order_by(DataConnector.id)).all()]


def _validate_connector(body: DataConnectorIn, db: Session) -> None:
    try:
        get_connector_class(body.connector_type)
    except ConnectorError as e:
        raise HTTPException(422, str(e))
    get_or_404(db, DataSource, body.data_source_id, "Data source")


@router.post("/connectors", status_code=201)
def create_connector(body: DataConnectorIn, user: User = MD, db: Session = Depends(get_db)):
    _validate_connector(body, db)
    c = DataConnector(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, user, "create", "data_connector", c.id, {"type": c.connector_type})
    db.commit()
    db.refresh(c)
    return connector_out(c)


@router.put("/connectors/{cid}")
def update_connector(cid: int, body: DataConnectorIn, user: User = MD, db: Session = Depends(get_db)):
    c = get_or_404(db, DataConnector, cid, "Connector")
    _validate_connector(body, db)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit(db, user, "update", "data_connector", c.id, {"is_enabled": c.is_enabled})
    db.commit()
    db.refresh(c)
    return connector_out(c)


@router.post("/connectors/{cid}/run")
def run_connector(cid: int, user: User = MD, db: Session = Depends(get_db)):
    c = get_or_404(db, DataConnector, cid, "Connector")
    if c.connector_type == "file_import":
        raise HTTPException(422, "File import connectors run via the upload endpoint")
    job = run_collection(db, source=c.data_source, connector=c, user=user, trigger="manual")
    return job_out(job)


# ---------- jobs
@router.get("/jobs", dependencies=[MD])
def list_jobs(source_id: int | None = None, p: PageParams = Depends(), db: Session = Depends(get_db)):
    stmt = select(CollectionJob)
    if source_id:
        stmt = stmt.where(CollectionJob.data_source_id == source_id)
    return paginate(db, stmt.order_by(CollectionJob.started_at.desc()), p, job_out)


@router.get("/jobs/{job_id}/logs", dependencies=[MD])
def job_logs(job_id: int, db: Session = Depends(get_db)):
    get_or_404(db, CollectionJob, job_id, "Job")
    rows = db.scalars(select(CollectionLog).where(CollectionLog.job_id == job_id).order_by(CollectionLog.id).limit(1000)).all()
    return [{"id": l.id, "level": l.level, "row_number": l.row_number, "message": l.message, "payload": l.payload,
             "created_at": l.created_at} for l in rows]


# ---------- import
@router.post("/import")
async def import_file(file: UploadFile = File(...), data_source_id: int = Form(...),
                      record_type: Literal["observation", "offer"] = Form("observation"),
                      allow_create_products: bool = Form(False), user: User = MD, db: Session = Depends(get_db)):
    ds = get_or_404(db, DataSource, data_source_id, "Data source")
    name = (file.filename or "").lower()
    if not name.endswith((".csv", ".xlsx")):
        raise HTTPException(415, "Only .csv and .xlsx files are accepted")
    limit = get_settings().max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"File exceeds {get_settings().max_upload_mb} MB")
    if name.endswith(".xlsx") and not content.startswith(b"PK"):
        raise HTTPException(415, "File content is not a valid XLSX")
    connector = db.scalar(select(DataConnector).where(DataConnector.data_source_id == ds.id,
                                                      DataConnector.connector_type == "file_import"))
    try:
        job = run_collection(db, source=ds, connector=connector, user=user, trigger="upload", file_name=file.filename,
                             content=content, filename=name, record_type=record_type,
                             allow_create_products=allow_create_products)
    except UnicodeDecodeError:
        raise HTTPException(422, "CSV must be UTF-8 encoded")
    audit(db, user, "import", "collection_job", job.id, {"file": file.filename, "status": job.status})
    db.commit()
    return job_out(job)


# ---------- product matching review
@router.get("/matches", dependencies=[MD])
def list_matches(status: str = "pending", p: PageParams = Depends(), db: Session = Depends(get_db)):
    stmt = select(ProductMatch).where(ProductMatch.status == status).order_by(ProductMatch.created_at.desc())
    return paginate(db, stmt, p, lambda m: {
        "id": m.id, "original_name": m.original_name, "score": m.score, "method": m.method, "reasons": m.reasons,
        "status": m.status, "raw_record": m.raw_record, "created_at": m.created_at, "data_source_id": m.data_source_id,
        "candidate": product_out(m.candidate_product) if m.candidate_product else None})


@router.post("/matches/{mid}")
def decide_match(mid: int, body: MatchDecision, user: User = MD, db: Session = Depends(get_db)):
    m = get_or_404(db, ProductMatch, mid, "Match")
    if m.status != "pending":
        raise HTTPException(409, "Already reviewed")
    result = None
    if body.action == "reject":
        m.status = "rejected"
    else:
        pid = body.product_id if body.action == "assign" else m.candidate_product_id
        if not pid or not db.get(Product, pid):
            raise HTTPException(422, "A valid product is required")
        ds = db.get(DataSource, m.data_source_id) if m.data_source_id else None
        if ds is None:
            raise HTTPException(422, "Original data source no longer exists")
        try:
            res = ingest_record(db, source=ds, rec=m.raw_record, collection_method="file_import", forced_product_id=pid)
        except RowError as e:
            raise HTTPException(422, str(e))
        m.status, m.candidate_product_id = "accepted", pid
        result = res.status
    m.reviewed_by_id, m.reviewed_at = user.id, utcnow()
    audit(db, user, f"match_{body.action}", "product_match", m.id, {"product_id": m.candidate_product_id})
    db.commit()
    return {"id": m.id, "status": m.status, "ingest_result": result}


# ---------- observations
@router.get("/observations", dependencies=[MD])
def list_observations(product_id: int | None = None, source_id: int | None = None, verification_status: str | None = None,
                      simulated: bool | None = None, p: PageParams = Depends(), db: Session = Depends(get_db)):
    stmt = select(PriceObservation)
    if product_id:
        stmt = stmt.where(PriceObservation.product_id == product_id)
    if source_id:
        stmt = stmt.where(PriceObservation.data_source_id == source_id)
    if verification_status:
        stmt = stmt.where(PriceObservation.verification_status == verification_status)
    if simulated is not None:
        stmt = stmt.where(PriceObservation.is_simulated.is_(simulated))
    return paginate(db, stmt.order_by(PriceObservation.collected_at.desc(), PriceObservation.id.desc()), p, observation_out)


@router.post("/observations", status_code=201)
def create_observation(body: ObservationIn, user: User = MD, db: Session = Depends(get_db)):
    prod = get_or_404(db, Product, body.product_id, "Product")
    unit = get_or_404(db, Unit, body.unit_id, "Unit")
    ds = get_or_404(db, DataSource, body.data_source_id, "Data source")
    get_or_404(db, Region, body.region_id, "Region")
    if body.supplier_id:
        get_or_404(db, Supplier, body.supplier_id, "Supplier")
    if body.observed_at > utcnow():
        raise HTTPException(422, "observed_at cannot be in the future")
    try:
        obs = record_observation(db, product=prod, unit=unit, price=body.price, currency=body.currency,
                                 region_id=body.region_id, price_type=body.price_type, data_source=ds,
                                 collection_method="manual", observed_at=body.observed_at, supplier_id=body.supplier_id,
                                 source_url=str(body.source_url) if body.source_url else None,
                                 original_product_name=body.original_product_name)
    except MissingExchangeRate as e:
        raise HTTPException(422, str(e))
    audit(db, user, "create", "price_observation", obs.id)
    db.commit()
    return observation_out(obs)


@router.post("/observations/{oid}/verification")
def verify_observation(oid: int, status: Literal["verified", "rejected", "unverified"], user: User = MD,
                       db: Session = Depends(get_db)):
    o = get_or_404(db, PriceObservation, oid, "Observation")
    o.verification_status = status  # review metadata only; price values stay immutable
    audit(db, user, "verification", "price_observation", o.id, {"status": status})
    db.commit()
    return observation_out(o)


@router.post("/observations/{oid}/outlier")
def mark_outlier(oid: int, is_outlier: bool, user: User = MD, db: Session = Depends(get_db)):
    o = get_or_404(db, PriceObservation, oid, "Observation")
    o.is_outlier = is_outlier
    audit(db, user, "mark_outlier", "price_observation", o.id, {"is_outlier": is_outlier})
    db.commit()
    return observation_out(o)


# ---------- verification queue
@router.get("/verification-requests", dependencies=[MD])
def verification_requests(status: str = "pending", db: Session = Depends(get_db)):
    rows = db.scalars(select(VerificationRequest).where(VerificationRequest.status == status)
                      .order_by(VerificationRequest.created_at.desc())).all()
    out = []
    for r in rows:
        name = None
        if r.target_type == "supplier":
            s = db.get(Supplier, r.target_id)
            name = s.name if s else None
        out.append({"id": r.id, "target_type": r.target_type, "target_id": r.target_id, "target_name": name,
                    "evidence": r.evidence, "status": r.status, "created_at": r.created_at})
    return out
