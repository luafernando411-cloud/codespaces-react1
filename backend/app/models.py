from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", use_alter=True))


class Profile(Base, TimestampMixin):
    __tablename__ = "perfis"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255))


class Permission(Base):
    __tablename__ = "permissoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class ProfilePermission(Base):
    __tablename__ = "perfis_permissoes"
    profile_id: Mapped[int] = mapped_column(ForeignKey("perfis.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissoes.id", ondelete="CASCADE"), primary_key=True)


class UserProfile(Base):
    __tablename__ = "usuarios_perfis"
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("perfis.id", ondelete="CASCADE"), primary_key=True)


class User(Base, TimestampMixin):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "sessoes_usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    refresh_jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Person(Base, TimestampMixin):
    __tablename__ = "pessoas"
    __table_args__ = (CheckConstraint("length(cpf) = 11", name="ck_pessoas_cpf_tamanho"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    social_name: Mapped[str | None] = mapped_column(String(160))
    birth_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    gender: Mapped[str | None] = mapped_column(String(30))
    marital_status: Mapped[str | None] = mapped_column(String(30))
    mother_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(254), index=True)


class Address(Base, TimestampMixin):
    __tablename__ = "enderecos"
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("pessoas.id", ondelete="CASCADE"), unique=True, index=True)
    postal_code: Mapped[str] = mapped_column(String(8), index=True)
    street: Mapped[str] = mapped_column(String(160))
    number: Mapped[str] = mapped_column(String(20))
    complement: Mapped[str | None] = mapped_column(String(100))
    neighborhood: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(2))


class Contact(Base, TimestampMixin):
    __tablename__ = "contatos"
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("pessoas.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(160), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BankDetails(Base, TimestampMixin):
    __tablename__ = "dados_bancarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("pessoas.id", ondelete="CASCADE"), unique=True, index=True)
    bank_code_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    branch_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    account_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)


class Organization(Base, TimestampMixin):
    __tablename__ = "orgaos_lotacoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    code: Mapped[str | None] = mapped_column(String(30), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("orgaos_lotacoes.id"))


class Position(Base, TimestampMixin):
    __tablename__ = "cargos"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    career_group: Mapped[str | None] = mapped_column(String(100))


class Insured(Base, TimestampMixin):
    __tablename__ = "segurados"
    __table_args__ = (CheckConstraint("tipo_vinculo IN ('ativo', 'aposentado', 'pensionista')", name="ck_segurado_tipo_vinculo"), Index("ix_segurados_situacao_tipo", "situacao", "tipo_vinculo"))
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("pessoas.id"), unique=True, nullable=False, index=True)
    tipo_vinculo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    situacao: Mapped[str] = mapped_column(String(30), default="ativo", nullable=False, index=True)
    registration_number: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    admission_date: Mapped[date | None] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date)


class ActiveEmployee(Base):
    __tablename__ = "servidores_ativos"
    insured_id: Mapped[int] = mapped_column(ForeignKey("segurados.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("orgaos_lotacoes.id"), index=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("cargos.id"), index=True)
    regime: Mapped[str] = mapped_column(String(40), nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class Retiree(Base):
    __tablename__ = "aposentados"
    insured_id: Mapped[int] = mapped_column(ForeignKey("segurados.id", ondelete="CASCADE"), primary_key=True)
    retirement_type: Mapped[str] = mapped_column(String(60), nullable=False)
    concession_date: Mapped[date] = mapped_column(Date, nullable=False)
    process_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    benefit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class Pensioner(Base):
    __tablename__ = "pensionistas"
    insured_id: Mapped[int] = mapped_column(ForeignKey("segurados.id", ondelete="CASCADE"), primary_key=True)
    institutor_id: Mapped[int] = mapped_column(ForeignKey("segurados.id"), nullable=False, index=True)
    kinship: Mapped[str] = mapped_column(String(50), nullable=False)
    death_date: Mapped[date] = mapped_column(Date, nullable=False)
    pension_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quota_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)


class DependentBeneficiary(Base, TimestampMixin):
    __tablename__ = "dependentes_beneficiarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    insured_id: Mapped[int] = mapped_column(ForeignKey("segurados.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("pessoas.id"), index=True)
    kinship: Mapped[str] = mapped_column(String(50), nullable=False)
    is_beneficiary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DocumentType(Base, TimestampMixin):
    __tablename__ = "tipos_documento"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    required_for: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    requires_expiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepted_mime_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_size_bytes: Mapped[int] = mapped_column(Integer, default=10485760, nullable=False)


class Document(Base, TimestampMixin):
    __tablename__ = "documentos"
    __table_args__ = (Index("ix_documentos_status_validade", "status", "validade"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    insured_id: Mapped[int] = mapped_column(ForeignKey("segurados.id", ondelete="CASCADE"), index=True)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("tipos_documento.id"), index=True)
    stored_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente", nullable=False, index=True)
    validade: Mapped[date | None] = mapped_column(Date, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    analyzed_by: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CensusCampaign(Base, TimestampMixin):
    __tablename__ = "campanhas_recenseamento"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_campanha_periodo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    target_audience: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planejada", nullable=False, index=True)


class Census(Base, TimestampMixin):
    __tablename__ = "recenseamentos"
    __table_args__ = (UniqueConstraint("insured_id", "campaign_id", name="uq_recenseamento_segurado_campanha"), Index("ix_recenseamentos_status_data", "status", "data"))
    id: Mapped[int] = mapped_column(primary_key=True)
    insured_id: Mapped[int] = mapped_column(ForeignKey("segurados.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campanhas_recenseamento.id", ondelete="CASCADE"), index=True)
    data: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente", nullable=False, index=True)
    responsible_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    risk_of_suspension: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AccessLog(Base):
    __tablename__ = "logs_acesso"
    __table_args__ = (Index("ix_logs_acesso_data_resultado", "data_hora", "sucesso"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    motivo: Mapped[str | None] = mapped_column(String(120))
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class AuditLog(Base):
    __tablename__ = "logs_auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    entidade: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entidade_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    acao: Mapped[str] = mapped_column(String(30), nullable=False)
    dados_antes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    dados_depois: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class GeneratedReport(Base):
    __tablename__ = "relatorios_gerados"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente", nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(String(255))
    requester_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SystemParameter(Base, TimestampMixin):
    __tablename__ = "parametros_sistema"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    default_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SystemParameterVersion(Base):
    __tablename__ = "parametros_versoes"
    __table_args__ = (UniqueConstraint("parameter_id", "version", name="uq_parametro_versao"), Index("ix_parametro_versoes_vigencia", "parameter_id", "valid_from", "valid_until"))
    id: Mapped[int] = mapped_column(primary_key=True)
    parameter_id: Mapped[int] = mapped_column(ForeignKey("parametros_sistema.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    changed_by: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ParameterApproval(Base):
    __tablename__ = "aprovacoes"
    __table_args__ = (Index("ix_aprovacoes_status_created", "status", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    requester_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    status: Mapped[str] = mapped_column(String(20), default="pendente", nullable=False, index=True)
    review_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BusinessEvent(Base):
    __tablename__ = "eventos_negocio"
    __table_args__ = (Index("ix_eventos_negocio_data_tipo", "occurred_at", "event_type"), Index("ix_eventos_negocio_entidade", "entity_type", "entity_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class TelemetryMetric(Base):
    __tablename__ = "metricas_brutas"
    __table_args__ = (Index("ix_metricas_brutas_serie_data", "series", "recorded_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    series: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class AlertRule(Base, TimestampMixin):
    __tablename__ = "regras_alerta"
    __table_args__ = (CheckConstraint("operator IN ('gt', 'gte', 'lt', 'lte')", name="ck_alert_rule_operator"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    metric: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operator: Mapped[str] = mapped_column(String(5), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Alert(Base):
    __tablename__ = "alertas"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("regras_alerta.id", ondelete="SET NULL"), index=True)
    deduplication_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    state: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DashboardLayout(Base):
    __tablename__ = "layouts_usuario"
    __table_args__ = (UniqueConstraint("user_id", "dashboard_key", name="uq_layout_usuario_dashboard"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    dashboard_key: Mapped[str] = mapped_column(String(80), nullable=False)
    layout: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
