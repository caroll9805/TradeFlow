import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

import app.services.market_data  # noqa: F401  (register connectors)
from app.api.routes import admin, analytics, assistant, auth, market_data, offers, procurement, products, reference, suppliers
from app.core.config import get_settings
from app.core.database import SessionLocal

log = logging.getLogger("tradeflow")
settings = get_settings()

if settings.environment == "production" and settings.jwt_secret in ("", "change-me-in-env"):
    raise RuntimeError("JWT_SECRET must be set in production")

app = FastAPI(title="TradeFlow API", version="0.1.0",
              description="Uzbekistan B2B market intelligence & procurement platform",
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})  # no internals leaked


for r in (auth, reference, products, suppliers, offers, analytics, assistant, procurement, market_data, admin):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health")
def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})
    finally:
        db.close()
