import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from jose import JWTError, jwt
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import admin_only, any_staff, auditor_or_admin, super_admin_only
from app.db import SessionLocal, get_db
from app.models import Alert, AlertRule, BusinessEvent, DashboardLayout, ParameterApproval, SystemParameter, SystemParameterVersion, TelemetryMetric, User, UserProfile, Profile
from app.observability import append_business_event, compare, evaluate_alerts, platform_snapshot, redis_client, verify_event_chain
from app.schemas import AlertRuleCreate, ApprovalReview, DashboardLayoutUpdate, MetricSample, ParameterUpdate
from app.services import AuditService

router = APIRouter()


PARAMETER_DEFAULTS: list[dict[str, Any]] = [
    {"code": "pension.census.frequency", "category": "recenseamento", "description": "Periodicidade da prova de vida", "value": "annual", "sensitive": False},
    {"code": "pension.census.allowed_channels", "category": "recenseamento", "description": "Canais permitidos para recenseamento", "value": ["presencial", "online"], "sensitive": False},
    {"code": "pension.census.suspension_threshold_days", "category": "recenseamento", "description": "Dias de tolerancia antes da suspensao", "value": 30, "sensitive": True},
    {"code": "documents.review_sla_days", "category": "documentos", "description": "SLA de analise documental em dias", "value": 5, "sensitive": False},
    {"code": "security.login_max_attempts", "category": "seguranca", "description": "Tentativas antes do bloqueio temporario", "value": 5, "sensitive": True},
    {"code": "security.session_minutes", "category": "seguranca", "description": "Duracao da sessao em minutos", "value": 15, "sensitive": True},
    {"code": "alerts.api_error_rate_percent", "category": "alertas", "description": "Taxa maxima de erro HTTP em percentual", "value": 5, "sensitive": True},
    {"code": "alerts.census_completion_min_percent", "category": "alertas", "description": "Conclusao minima da campanha em percentual", "value": 80, "sensitive": False},
]
SENSITIVE_PARAMETER_PREFIXES = ("security.", "tenancy.", "admin.")
ALLOWED_METRICS = {"http.requests.total", "http.errors.total", "http.request.duration_ms", "logins.success", "logins.failure", "insured.created", "documents.pending", "census.completed", "reports.queue_size"}


def _latest_version(db: Session, parameter_id: int) -> SystemParameterVersion | None:
    return db.scalar(select(SystemParameterVersion).where(SystemParameterVersion.parameter_id == parameter_id, SystemParameterVersion.valid_until.is_(None)).order_by(SystemParameterVersion.version.desc()).limit(1))


def _validate_parameter_value(parameter: SystemParameter, value: Any) -> None:
    current = parameter.default_value
    if isinstance(current, bool) and not isinstance(value, bool):
        raise HTTPException(status_code=422, detail="Valor deve ser booleano")
    if isinstance(current, int) and not isinstance(current, bool) and (not isinstance(value, int) or value < 0 or value > 100000):
        raise HTTPException(status_code=422, detail="Valor inteiro fora do intervalo permitido")
    if isinstance(current, float) and not isinstance(value, (int, float)):
        raise HTTPException(status_code=422, detail="Valor deve ser numerico")
    if isinstance(current, str) and not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Valor deve ser texto")
    if isinstance(current, list) and (not isinstance(value, list) or len(value) > 50):
        raise HTTPException(status_code=422, detail="Valor deve ser uma lista com ate 50 itens")
    if isinstance(current, dict) and not isinstance(value, dict):
        raise HTTPException(status_code=422, detail="Valor deve ser um objeto")
    if parameter.code == "pension.census.frequency" and value not in {"monthly_birthday", "annual", "campaign"}:
        raise HTTPException(status_code=422, detail="Periodicidade previdenciaria nao suportada")
    if parameter.code == "pension.census.allowed_channels" and not set(value).issubset({"presencial", "online", "representante_legal"}):
        raise HTTPException(status_code=422, detail="Canal de recenseamento nao suportado")
    if parameter.code.endswith("percent") and not 0 <= value <= 100:
        raise HTTPException(status_code=422, detail="Percentual deve estar entre 0 e 100")


def _parameter_json(db: Session, item: SystemParameter) -> dict:
    version = _latest_version(db, item.id)
    return {"id": item.id, "code": item.code, "category": item.category, "description": item.description, "value": version.value if version else item.default_value, "default_value": item.default_value, "sensitive": item.sensitive, "version": version.version if version else 0, "valid_from": version.valid_from if version else None, "changed_by": version.changed_by if version else None}


def _apply_parameter(db: Session, parameter: SystemParameter, value: Any, actor_id: int, reason: str) -> SystemParameterVersion:
    now = datetime.now(timezone.utc)
    current = _latest_version(db, parameter.id)
    if current:
        current.valid_until = now
    version = SystemParameterVersion(parameter_id=parameter.id, version=(current.version + 1) if current else 1, value=value, valid_from=now, changed_by=actor_id, change_reason=reason)
    db.add(version)
    AuditService(db).record(actor_id, "parametros_sistema", parameter.code, "nova_versao", before={"version": current.version, "value": current.value} if current else None, after={"version": version.version, "value": value})
    append_business_event(db, "parameter.updated", "parametros_sistema", parameter.code, actor_id, {"version": version.version, "reason": reason})
    return version


@router.post("/configuracoes/parametros/seed", status_code=200)
def seed_parameters(actor: User = Depends(admin_only), db: Session = Depends(get_db)):
    inserted = 0
    for item in PARAMETER_DEFAULTS:
        parameter = db.scalar(select(SystemParameter).where(SystemParameter.code == item["code"]))
        if parameter:
            continue
        parameter = SystemParameter(code=item["code"], category=item["category"], description=item["description"], default_value=item["value"], sensitive=item["sensitive"], enabled=True, created_by=actor.id)
        db.add(parameter)
        db.flush()
        _apply_parameter(db, parameter, item["value"], actor.id, "Carga inicial de parametros padrao")
        inserted += 1
    db.commit()
    return {"inserted": inserted}


@router.get("/configuracoes/parametros")
def list_parameters(_: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    return [_parameter_json(db, item) for item in db.scalars(select(SystemParameter).where(SystemParameter.enabled.is_(True), SystemParameter.deleted_at.is_(None)).order_by(SystemParameter.category, SystemParameter.code))]


@router.put("/configuracoes/parametros/{code}")
def update_parameter(code: str, data: ParameterUpdate, actor: User = Depends(admin_only), db: Session = Depends(get_db)):
    parameter = db.scalar(select(SystemParameter).where(SystemParameter.code == code, SystemParameter.enabled.is_(True), SystemParameter.deleted_at.is_(None)))
    if not parameter:
        raise HTTPException(status_code=404, detail="Parametro nao encontrado")
    _validate_parameter_value(parameter, data.value)
    sensitive = parameter.sensitive or code.startswith(SENSITIVE_PARAMETER_PREFIXES)
    if sensitive:
        approval = ParameterApproval(resource_type="system_parameter", resource_key=code, requested_value={"value": data.value}, reason=data.reason, requester_id=actor.id, status="pendente")
        db.add(approval)
        db.flush()
        append_business_event(db, "approval.requested", "parametros_sistema", code, actor.id, {"approval_id": approval.id, "reason": data.reason})
        db.commit()
        return {"status": "aguardando_aprovacao", "approval_id": approval.id}
    version = _apply_parameter(db, parameter, data.value, actor.id, data.reason)
    db.commit()
    return {"status": "aplicado", "parameter": _parameter_json(db, parameter), "version": version.version}


@router.get("/configuracoes/parametros/{code}/historico")
def parameter_history(code: str, _: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    parameter = db.scalar(select(SystemParameter).where(SystemParameter.code == code))
    if not parameter:
        raise HTTPException(status_code=404, detail="Parametro nao encontrado")
    versions = db.scalars(select(SystemParameterVersion).where(SystemParameterVersion.parameter_id == parameter.id).order_by(SystemParameterVersion.version.desc()))
    return [{"version": item.version, "value": item.value, "valid_from": item.valid_from, "valid_until": item.valid_until, "changed_by": item.changed_by, "change_reason": item.change_reason} for item in versions]


@router.get("/configuracoes/aprovacoes")
def list_approvals(status_filter: str = "pendente", _: User = Depends(super_admin_only), db: Session = Depends(get_db)):
    records = db.scalars(select(ParameterApproval).where(ParameterApproval.status == status_filter).order_by(ParameterApproval.created_at.desc()).limit(200))
    return [{"id": item.id, "resource_type": item.resource_type, "resource_key": item.resource_key, "requested_value": item.requested_value, "reason": item.reason, "requester_id": item.requester_id, "status": item.status, "created_at": item.created_at} for item in records]


@router.post("/configuracoes/aprovacoes/{approval_id}/revisao")
def review_approval(approval_id: int, data: ApprovalReview, reviewer: User = Depends(super_admin_only), db: Session = Depends(get_db)):
    approval = db.get(ParameterApproval, approval_id)
    if not approval or approval.status != "pendente":
        raise HTTPException(status_code=404, detail="Aprovacao pendente nao encontrada")
    if approval.requester_id == reviewer.id:
        raise HTTPException(status_code=403, detail="Quem solicitou nao pode aprovar a propria alteracao")
    approval.reviewer_id = reviewer.id
    approval.reviewed_at = datetime.now(timezone.utc)
    approval.review_reason = data.reason
    approval.status = data.decision
    if data.decision == "aprovado" and approval.resource_type == "system_parameter":
        parameter = db.scalar(select(SystemParameter).where(SystemParameter.code == approval.resource_key))
        if not parameter:
            raise HTTPException(status_code=404, detail="Parametro nao encontrado")
        _apply_parameter(db, parameter, approval.requested_value["value"], reviewer.id, f"Aprovado por usuario {reviewer.id}: {data.reason}")
    AuditService(db).record(reviewer.id, "aprovacoes", approval.id, data.decision, before={"status": "pendente"}, after={"status": approval.status, "requester_id": approval.requester_id})
    append_business_event(db, f"approval.{data.decision}", "aprovacoes", approval.id, reviewer.id, {"resource": approval.resource_key, "requester_id": approval.requester_id})
    db.commit()
    return {"id": approval.id, "status": approval.status, "reviewed_at": approval.reviewed_at}


@router.post("/monitoramento/regras", status_code=201)
def create_alert_rule(data: AlertRuleCreate, actor: User = Depends(admin_only), db: Session = Depends(get_db)):
    if data.metric not in ALLOWED_METRICS:
        raise HTTPException(status_code=422, detail="Serie de metrica nao permitida")
    rule = AlertRule(**data.model_dump(), created_by=actor.id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    append_business_event(db, "alert_rule.created", "regras_alerta", rule.id, actor.id, {"metric": rule.metric, "threshold": str(rule.threshold)})
    db.commit()
    return {"id": rule.id, "name": rule.name, "metric": rule.metric, "operator": rule.operator, "threshold": rule.threshold, "severity": rule.severity, "enabled": rule.enabled}


@router.get("/monitoramento/regras")
def list_alert_rules(_: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    return [{"id": rule.id, "name": rule.name, "metric": rule.metric, "operator": rule.operator, "threshold": rule.threshold, "severity": rule.severity, "window_seconds": rule.window_seconds, "enabled": rule.enabled} for rule in db.scalars(select(AlertRule).where(AlertRule.deleted_at.is_(None)).order_by(AlertRule.name))]


@router.get("/monitoramento/alertas")
def list_alerts(state: str | None = "open", _: User = Depends(any_staff), db: Session = Depends(get_db)):
    statement = select(Alert).order_by(Alert.last_seen_at.desc()).limit(200)
    if state:
        statement = statement.where(Alert.state == state)
    return [{"id": alert.id, "severity": alert.severity, "title": alert.title, "message": alert.message, "value": alert.value, "state": alert.state, "first_seen_at": alert.first_seen_at, "last_seen_at": alert.last_seen_at, "acknowledged_by": alert.acknowledged_by} for alert in db.scalars(statement)]


@router.post("/monitoramento/alertas/{alert_id}/ack")
def acknowledge_alert(alert_id: int, actor: User = Depends(any_staff), db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta nao encontrado")
    alert.state, alert.acknowledged_by, alert.acknowledged_at = "acknowledged", actor.id, datetime.now(timezone.utc)
    append_business_event(db, "alert.acknowledged", "alertas", alert.id, actor.id, {"severity": alert.severity})
    db.commit()
    return {"id": alert.id, "state": alert.state}


@router.post("/monitoramento/metricas", status_code=202)
def ingest_metric(data: MetricSample, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    if data.series not in ALLOWED_METRICS:
        raise HTTPException(status_code=422, detail="Serie de metrica nao permitida")
    recorded_at = data.recorded_at or datetime.now(timezone.utc)
    metric = TelemetryMetric(series=data.series, value=data.value, labels=data.labels, recorded_at=recorded_at)
    db.add(metric)
    triggered = evaluate_alerts(db, data.series, data.value, recorded_at)
    append_business_event(db, "metric.recorded", "metricas_brutas", data.series, None, {"value": str(data.value), "labels": data.labels})
    db.commit()
    client = redis_client()
    if client:
        try:
            client.publish("aurora:telemetry", json.dumps({"series": data.series, "value": str(data.value), "recorded_at": recorded_at.isoformat()}))
        except Exception:
            pass
    return {"stored": True, "alerts_triggered": len(triggered)}


@router.get("/monitoramento/central")
def monitoring_dashboard(minutes: int = 60, _: User = Depends(any_staff), db: Session = Depends(get_db)):
    if minutes not in {5, 60, 1440, 10080}:
        raise HTTPException(status_code=422, detail="Intervalo permitido: 5, 60, 1440 ou 10080 minutos")
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    snapshot = platform_snapshot(db)
    metric_rows = db.execute(select(TelemetryMetric.series, TelemetryMetric.recorded_at, TelemetryMetric.value, TelemetryMetric.labels).where(TelemetryMetric.recorded_at >= since).order_by(TelemetryMetric.recorded_at).limit(5000)).all()
    series: dict[str, list[dict]] = {}
    for name, recorded_at, value, labels in metric_rows:
        series.setdefault(name, []).append({"at": recorded_at.isoformat(), "value": float(value), "labels": labels})
    events = db.scalars(select(BusinessEvent).where(BusinessEvent.occurred_at >= since).order_by(BusinessEvent.id.desc()).limit(50)).all()
    snapshot.update({"interval_minutes": minutes, "series": series, "events": [{"id": event.id, "event_type": event.event_type, "entity_type": event.entity_type, "occurred_at": event.occurred_at.isoformat(), "payload": event.payload} for event in events], "event_chain_valid": verify_event_chain(db)})
    return snapshot


@router.get("/monitoramento/eventos")
def list_business_events(after_id: int = 0, limit: int = 100, _: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 500)
    events = db.scalars(select(BusinessEvent).where(BusinessEvent.id > after_id).order_by(BusinessEvent.id).limit(limit)).all()
    return [{"id": event.id, "event_type": event.event_type, "entity_type": event.entity_type, "entity_id": event.entity_id, "actor_id": event.actor_id, "payload": event.payload, "occurred_at": event.occurred_at, "previous_hash": event.previous_hash, "event_hash": event.event_hash} for event in events]


@router.get("/monitoramento/eventos/integridade")
def event_chain_integrity(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return {"valid": verify_event_chain(db)}


@router.get("/monitoramento/layout/{dashboard_key}")
def get_layout(dashboard_key: str, user: User = Depends(any_staff), db: Session = Depends(get_db)):
    layout = db.scalar(select(DashboardLayout).where(DashboardLayout.user_id == user.id, DashboardLayout.dashboard_key == dashboard_key))
    return {"dashboard_key": dashboard_key, "layout": layout.layout if layout else []}


@router.put("/monitoramento/layout/{dashboard_key}")
def save_layout(dashboard_key: str, data: DashboardLayoutUpdate, user: User = Depends(any_staff), db: Session = Depends(get_db)):
    layout = db.scalar(select(DashboardLayout).where(DashboardLayout.user_id == user.id, DashboardLayout.dashboard_key == dashboard_key))
    if layout:
        layout.layout = data.layout
    else:
        layout = DashboardLayout(user_id=user.id, dashboard_key=dashboard_key, layout=data.layout)
        db.add(layout)
    db.commit()
    return {"dashboard_key": dashboard_key, "layout": layout.layout}


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.websocket("/monitoramento/ws")
async def monitoring_websocket(websocket: WebSocket, token: str, channel: str = "all", after_id: int = 0):
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if claims.get("type") != "access":
            raise ValueError("wrong token type")
        user_id = int(claims["sub"])
    except (JWTError, ValueError, KeyError, TypeError):
        await websocket.close(code=4401, reason="Autenticacao necessaria")
        return
    with SessionLocal() as db:
        user = db.get(User, user_id)
        profile_codes = list(db.scalars(select(Profile.code).join(UserProfile).where(UserProfile.user_id == user_id))) if user else []
        if not user or not user.is_active or not set(profile_codes).intersection({"administrador", "operador", "auditor"}):
            await websocket.close(code=4403, reason="Acesso negado")
            return
    if channel not in {"all", "acessos", "cadastros", "recenseamento", "saude", "alertas"}:
        await websocket.close(code=4400, reason="Canal invalido")
        return
    await websocket.accept()
    await websocket.send_json({"type": "connection", "status": "live", "channel": channel, "at": datetime.now(timezone.utc).isoformat()})
    last_event_id = max(0, after_id)
    redis = redis_client()
    pubsub = redis.pubsub() if redis else None
    if pubsub:
        try:
            pubsub.subscribe("aurora:business-events", "aurora:telemetry")
        except Exception:
            pubsub = None
    try:
        while True:
            message = None
            if pubsub:
                try:
                    message = await asyncio.to_thread(pubsub.get_message, True, 1.0)
                except Exception:
                    pubsub = None
            else:
                await asyncio.sleep(1)
            if message and message.get("type") == "message":
                try:
                    payload = json.loads(message["data"])
                    event_channel = "saude" if "series" in payload else "all"
                    if event_channel == "saude" and (channel == "all" or channel == event_channel):
                        await websocket.send_json({"type": event_channel, "data": payload, "at": datetime.now(timezone.utc).isoformat()})
                except (ValueError, TypeError):
                    pass
            with SessionLocal() as db:
                events = db.scalars(select(BusinessEvent).where(BusinessEvent.id > last_event_id).order_by(BusinessEvent.id).limit(100)).all()
                for event in events:
                    last_event_id = event.id
                    event_channel = _channel_for_event(event.event_type)
                    if channel == "all" or channel == event_channel:
                        await websocket.send_json({"type": event_channel, "id": event.id, "event_type": event.event_type, "entity_type": event.entity_type, "occurred_at": event.occurred_at.isoformat(), "payload": event.payload})
            await websocket.send_json({"type": "heartbeat", "at": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        pass
    finally:
        if pubsub:
            try:
                pubsub.close()
            except Exception:
                pass


def _channel_for_event(event_type: str) -> str:
    if event_type.startswith(("login.", "access.")):
        return "acessos"
    if "census" in event_type or "recense" in event_type:
        return "recenseamento"
    if "alert" in event_type:
        return "alertas"
    if event_type.startswith(("insured.", "document.")):
        return "cadastros"
    return "all"
