import os
import tempfile
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-with-at-least-32-characters")
os.environ.setdefault("ADMIN_CPF", "52998224725")
os.environ.setdefault("ADMIN_PASSWORD", "ChangeMe!2026")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.core.security import hash_password
from app.db import Base, get_db
from app.main import app
from app.models import Profile, User, UserProfile


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    import app.db as db_module
    import app.main as main_module
    monkeypatch.setattr(db_module, "SessionLocal", TestingSession)
    monkeypatch.setattr(main_module, "SessionLocal", TestingSession)
    monkeypatch.setattr(main_module, "engine", engine)
    with TestingSession() as session:
        admin_profile = Profile(name="Administrador", code="administrador")
        super_admin_profile = Profile(name="Super Administrador", code="super_administrador")
        operator_profile = Profile(name="Operador", code="operador")
        auditor_profile = Profile(name="Auditor", code="auditor")
        session.add_all([admin_profile, super_admin_profile, operator_profile, auditor_profile])
        session.flush()
        admin = User(cpf="52998224725", email="admin@example.test", full_name="Admin Teste", password_hash=hash_password("ChangeMe!2026"))
        operator = User(cpf="11144477735", email="operador@example.test", full_name="Operador Teste", password_hash=hash_password("ChangeMe!2026"))
        auditor = User(cpf="93541134780", email="auditor@example.test", full_name="Auditor Teste", password_hash=hash_password("ChangeMe!2026"))
        session.add_all([admin, operator, auditor])
        session.flush()
        session.add_all([UserProfile(user_id=admin.id, profile_id=admin_profile.id), UserProfile(user_id=admin.id, profile_id=super_admin_profile.id), UserProfile(user_id=operator.id, profile_id=operator_profile.id), UserProfile(user_id=auditor.id, profile_id=auditor_profile.id)])
        session.commit()
    with TestClient(app, client=(f"test-{uuid4().hex}", 50000)) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def access_token(client, cpf="52998224725"):
    response = client.post("/api/v1/auth/login", json={"cpf": cpf, "password": "ChangeMe!2026"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_and_login(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
    token = access_token(client)
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert set(profile.json()["profiles"]) == {"administrador", "super_administrador"}


def test_login_blocks_after_five_failures(client):
    for _ in range(5):
        response = client.post("/api/v1/auth/login", json={"cpf": "52998224725", "password": "wrong"})
        assert response.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"cpf": "52998224725", "password": "ChangeMe!2026"})
    assert blocked.status_code == 423


def test_rbac_and_insured_creation(client):
    operator_token = access_token(client, "11144477735")
    auditor_token = access_token(client, "93541134780")
    payload = {"cpf": "11122233396", "full_name": "Servidor de Teste", "birth_date": "1985-02-03", "tipo_vinculo": "ativo", "registration_number": "MAT-01", "admission_date": "2010-03-01", "regime": "RPPS", "base_salary": 5400}
    created = client.post("/api/v1/segurados", json=payload, headers={"Authorization": f"Bearer {operator_token}"})
    assert created.status_code == 201
    assert created.json()["cpf"] == "***.***.333-**"
    denied = client.post("/api/v1/segurados", json={**payload, "cpf": "52998224725", "registration_number": "MAT-02"}, headers={"Authorization": f"Bearer {auditor_token}"})
    assert denied.status_code == 403
    listed = client.get("/api/v1/segurados", headers={"Authorization": f"Bearer {auditor_token}"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_invalid_cpf_and_report_export(client):
    token = access_token(client)
    invalid = client.post("/api/v1/segurados", json={"cpf": "12345678900", "full_name": "CPF Invalido", "birth_date": "1990-01-01", "tipo_vinculo": "ativo"}, headers={"Authorization": f"Bearer {token}"})
    assert invalid.status_code == 422
    report = client.post("/api/v1/relatorios", json={"type": "segurados_por_vinculo", "format": "csv"}, headers={"Authorization": f"Bearer {token}"})
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    assert "nome" in report.text


def test_dashboard_returns_database_aggregates(client):
    token = access_token(client)
    response = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["segurados_total"] == 0
    assert len(response.json()["cadastros_por_mes"]) == 6
    assert response.json()["recentes"] == []


def test_enterprise_parameters_approvals_alerts_and_integrity(client):
    token = access_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    seeded = client.post("/api/v1/configuracoes/parametros/seed", headers=headers)
    assert seeded.status_code == 200
    assert seeded.json()["inserted"] == 8

    update = client.put("/api/v1/configuracoes/parametros/documents.review_sla_days", json={"value": 7, "reason": "Ajuste do SLA documental"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["version"] == 2
    history = client.get("/api/v1/configuracoes/parametros/documents.review_sla_days/historico", headers=headers)
    assert [version["version"] for version in history.json()] == [2, 1]

    sensitive = client.put("/api/v1/configuracoes/parametros/security.session_minutes", json={"value": 20, "reason": "Ajuste de politica de sessao"}, headers=headers)
    assert sensitive.status_code == 200
    approval_id = sensitive.json()["approval_id"]
    self_approval = client.post(f"/api/v1/configuracoes/aprovacoes/{approval_id}/revisao", json={"decision": "aprovado", "reason": "Tentativa de autoaprovacao"}, headers=headers)
    assert self_approval.status_code == 403

    rule = client.post("/api/v1/monitoramento/regras", json={"name": "Falhas de login elevadas", "metric": "logins.failure", "operator": "gte", "threshold": 3, "severity": "critical", "window_seconds": 60}, headers=headers)
    assert rule.status_code == 201
    sample = client.post("/api/v1/monitoramento/metricas", json={"series": "logins.failure", "value": 3, "labels": {"profile": "operador"}}, headers=headers)
    assert sample.status_code == 202
    assert sample.json()["alerts_triggered"] == 1
    alert = client.get("/api/v1/monitoramento/alertas", headers=headers).json()[0]
    acknowledged = client.post(f"/api/v1/monitoramento/alertas/{alert['id']}/ack", headers=headers)
    assert acknowledged.json()["state"] == "acknowledged"

    monitoring = client.get("/api/v1/monitoramento/central?minutes=60", headers=headers)
    assert monitoring.status_code == 200
    assert monitoring.json()["event_chain_valid"] is True
    assert monitoring.json()["series"]["logins.failure"][0]["value"] == 3
    assert client.get("/metrics").status_code == 200


def test_monitoring_websocket_requires_and_accepts_access_token(client):
    token = access_token(client)
    with client.websocket_connect(f"/api/v1/monitoramento/ws?token={token}&channel=saude") as socket:
        message = socket.receive_json()
        assert message["type"] == "connection"
        assert message["status"] == "live"
        assert message["channel"] == "saude"


def test_react_fallback_serves_spa_but_not_unknown_api(client, monkeypatch, tmp_path):
    import app.main as main_module

    (tmp_path / "index.html").write_text("<main>React SPA</main>", encoding="utf-8")
    monkeypatch.setattr(main_module, "DIST_DIR", tmp_path)

    assert client.get("/").text == "<main>React SPA</main>"
    assert client.get("/segurados/novo").text == "<main>React SPA</main>"
    missing_api = client.get("/api/v1/rota-inexistente")
    assert missing_api.status_code == 404
    assert missing_api.json()["error"]["code"] == "not_found"
