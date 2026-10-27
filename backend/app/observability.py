import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache

import psutil
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import engine
from app.models import Alert, AlertRule, BusinessEvent

ZERO_HASH = "0" * 64


@lru_cache(maxsize=1)
def redis_client() -> Redis | None:
    if not settings.redis_url:
        return None
    return Redis.from_url(settings.redis_url, socket_connect_timeout=0.25, socket_timeout=0.25, decode_responses=True)


def append_business_event(db: Session, event_type: str, entity_type: str, entity_id: int | str | None, actor_id: int | None, payload: dict, idempotency_key: str | None = None) -> BusinessEvent:
    if idempotency_key:
        existing = db.scalar(select(BusinessEvent).where(BusinessEvent.idempotency_key == idempotency_key))
        if existing:
            return existing
    previous = db.scalar(select(BusinessEvent).order_by(BusinessEvent.id.desc()).limit(1))
    previous_hash = previous.event_hash if previous else ZERO_HASH
    occurred_at = datetime.now(timezone.utc)
    canonical = json.dumps({"type": event_type, "entity": entity_type, "entity_id": str(entity_id) if entity_id is not None else None, "actor_id": actor_id, "payload": payload, "occurred_at": occurred_at.isoformat(), "previous_hash": previous_hash}, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    event_hash = hashlib.sha256(canonical.encode()).hexdigest()
    event = BusinessEvent(event_type=event_type, entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None, actor_id=actor_id, payload=payload, idempotency_key=idempotency_key, previous_hash=previous_hash, event_hash=event_hash, occurred_at=occurred_at)
    db.add(event)
    db.flush()
    client = redis_client()
    if client:
        try:
            client.publish("aurora:business-events", json.dumps({"id": event.id, "event_type": event_type, "entity_type": entity_type, "entity_id": event.entity_id, "occurred_at": occurred_at.isoformat()}))
        except Exception:
            pass
    return event


def compare(value: Decimal, operator: str, threshold: Decimal) -> bool:
    return {"gt": value > threshold, "gte": value >= threshold, "lt": value < threshold, "lte": value <= threshold}[operator]


def evaluate_alerts(db: Session, metric: str, value: Decimal, recorded_at: datetime) -> list[Alert]:
    triggered = []
    rules = db.scalars(select(AlertRule).where(AlertRule.metric == metric, AlertRule.enabled.is_(True), AlertRule.deleted_at.is_(None))).all()
    for rule in rules:
        if not compare(value, rule.operator, rule.threshold):
            continue
        bucket = int(recorded_at.timestamp()) // rule.window_seconds
        key = f"rule:{rule.id}:{bucket}"
        alert = db.scalar(select(Alert).where(Alert.deduplication_key == key))
        if alert:
            alert.last_seen_at = recorded_at
            alert.value = value
        else:
            alert = Alert(rule_id=rule.id, deduplication_key=key, severity=rule.severity, title=rule.name, message=f"{metric} atingiu {value}; limite configurado: {rule.operator} {rule.threshold}", value=value, state="open", first_seen_at=recorded_at, last_seen_at=recorded_at)
            db.add(alert)
            db.flush()
            append_business_event(db, "alert.triggered", "alertas", alert.id, None, {"rule_id": rule.id, "metric": metric, "value": str(value), "severity": rule.severity})
        triggered.append(alert)
    return triggered


def platform_snapshot(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        database_status = "online"
    except Exception:
        database_status = "offline"
    client = redis_client()
    if client is None:
        redis_status = "disabled"
    else:
        try:
            redis_status = "online" if client.ping() else "offline"
        except Exception:
            redis_status = "offline"
    process = psutil.Process()
    memory = psutil.virtual_memory()
    try:
        pool = engine.pool
        pool_size = pool.size()
        pool_checked_out = pool.checkedout() if hasattr(pool, "checkedout") else 0
        pool_occupancy = round(pool_checked_out / max(pool_size, 1) * 100, 1)
    except Exception:
        pool_occupancy = 0
    online_sessions = db.scalar(select(Alert.id).where(Alert.state == "open").limit(1))
    return {"status": {"api": "online", "database": database_status, "redis": redis_status}, "system": {"cpu_percent": psutil.cpu_percent(interval=None), "memory_percent": memory.percent, "process_memory_mb": round(process.memory_info().rss / 1024 / 1024, 1), "pool_occupancy_percent": pool_occupancy}, "server_time": now.isoformat(), "updated_at": now.isoformat(), "online_users": 0, "open_alerts": bool(online_sessions)}


def verify_event_chain(db: Session) -> bool:
    previous_hash = ZERO_HASH
    events = db.scalars(select(BusinessEvent).order_by(BusinessEvent.id)).all()
    for event in events:
        canonical = json.dumps({"type": event.event_type, "entity": event.entity_type, "entity_id": event.entity_id, "actor_id": event.actor_id, "payload": event.payload, "occurred_at": event.occurred_at.isoformat(), "previous_hash": previous_hash}, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
        if event.previous_hash != previous_hash or hashlib.sha256(canonical.encode()).hexdigest() != event.event_hash:
            return False
        previous_hash = event.event_hash
    return True
