import json
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api import limiter, router
from app.enterprise_api import router as enterprise_router
from app.core.config import settings
from app.core.dependencies import oauth2_scheme
from app.core.security import decode_token
from app.db import SessionLocal, engine
from app.models import AccessLog
from app.observability import append_business_event


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "message": record.getMessage()}, ensure_ascii=True)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("aurora.api")
HTTP_REQUESTS = Counter("aurora_http_requests_total", "HTTP requests received", ("method", "path", "status"))
HTTP_DURATION = Histogram("aurora_http_request_duration_seconds", "HTTP request duration", ("method", "path"))

app = FastAPI(title=settings.app_name, version="1.0.0", docs_url="/docs", redoc_url="/redoc")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": {"code": "rate_limit", "message": "Muitas tentativas. Aguarde antes de tentar novamente."}})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    details = jsonable_encoder(exc.errors(), custom_encoder={ValueError: str})
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Dados de entrada invalidos", "details": details}})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("request_failed path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "Erro interno do servidor"}})


@app.middleware("http")
async def access_audit(request: Request, call_next):
    started = time.monotonic()
    correlation_id = request.headers.get("x-correlation-id", str(uuid4()))[:80]
    user_id = None
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            claims = decode_token(authorization[7:], "access")
            user_id = int(claims["sub"])
        except (ValueError, KeyError, TypeError):
            pass
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_exception method=%s path=%s", request.method, request.url.path)
        raise
    finally:
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        response_status = getattr(locals().get("response"), "status_code", 500)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, route_path, str(response_status)).inc()
        HTTP_DURATION.labels(request.method, route_path).observe(time.monotonic() - started)
        logger.info("request method=%s path=%s status=%s duration_ms=%s correlation_id=%s", request.method, route_path, response_status, duration_ms, correlation_id)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path not in ("/health", "/docs", "/openapi.json", "/redoc") and not request.url.path.endswith(("/auth/login", "/auth/refresh")):
        try:
            with SessionLocal() as db:
                db.add(AccessLog(user_id=user_id, ip=request.client.host if request.client else "unknown", user_agent=request.headers.get("user-agent", "")[:500], sucesso=response.status_code < 400, motivo=f"http_{response.status_code}"))
                db.commit()
        except Exception:
            logger.exception("access_log_write_failed")
    return response


app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])
app.include_router(router, prefix="/api/v1")
app.include_router(enterprise_router, prefix="/api/v1")


@app.get("/health", tags=["infra"], include_in_schema=True)
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception as exc:
        logger.error("health_database_failed error=%s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})


@app.get("/metrics", tags=["infra"], include_in_schema=False)
def metrics():
    from fastapi.responses import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
