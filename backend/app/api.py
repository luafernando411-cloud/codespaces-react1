from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.dependencies import admin_only, any_staff, auditor_or_admin, get_current_user, operator_or_admin
from app.core.security import create_token, hash_password, verify_password
from app.db import get_db
from app.models import AccessLog, AuditLog, Census, CensusCampaign, Document, DocumentType, Insured, Person, Profile, User, UserProfile, UserSession
from app.repositories import InsuredRepository
from app.schemas import CampaignCreate, CensusCreate, DocumentReview, DocumentTypeCreate, InsuredCreate, LoginRequest, PasswordChange, RefreshRequest, ReportRequest, UserCreate
from app.services import AuditService, CensusService, DocumentService, InsuredService

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _mask_cpf(cpf: str) -> str:
    return f"***.***.{cpf[6:9]}-**"


def _user_payload(user: User, profiles: list[str]) -> dict:
    return {"id": user.id, "cpf": _mask_cpf(user.cpf), "email": user.email, "full_name": user.full_name, "is_active": user.is_active, "profiles": profiles}


def _issue_pair(user: User, db: Session) -> dict:
    access, _ = create_token(str(user.id), "access", timedelta(minutes=settings.access_token_minutes))
    refresh, refresh_jti = create_token(str(user.id), "refresh", timedelta(days=settings.refresh_token_days))
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    db.add(UserSession(user_id=user.id, refresh_jti=refresh_jti, expires_at=expires))
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": settings.access_token_minutes * 60}


@router.post("/auth/login")
@limiter.limit("10/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.cpf == data.cpf, User.deleted_at.is_(None)))
    now = datetime.now(timezone.utc)
    remote_ip = get_remote_address(request)
    user_agent = request.headers.get("user-agent", "")[:500]
    if user and user.locked_until:
        lock_time = user.locked_until.replace(tzinfo=timezone.utc) if user.locked_until.tzinfo is None else user.locked_until
        if lock_time > now:
            db.add(AccessLog(user_id=user.id, ip=remote_ip, user_agent=user_agent, sucesso=False, motivo="conta_bloqueada"))
            db.commit()
            raise HTTPException(status_code=423, detail="Conta temporariamente bloqueada")
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= settings.login_max_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        db.add(AccessLog(user_id=user.id if user else None, ip=remote_ip, user_agent=user_agent, sucesso=False, motivo="credenciais_invalidas"))
        db.commit()
        raise HTTPException(status_code=401, detail="CPF ou senha invalidos")
    user.failed_attempts = 0
    user.locked_until = None
    db.add(AccessLog(user_id=user.id, ip=remote_ip, user_agent=user_agent, sucesso=True, motivo="login"))
    result = _issue_pair(user, db)
    return {**result, "user": _user_payload(user, list(db.scalars(select(Profile.code).join(UserProfile).where(UserProfile.user_id == user.id))))}


@router.post("/auth/refresh")
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise ValueError("wrong token type")
        user_id, token_id = int(payload["sub"]), payload["jti"]
    except (JWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Refresh token invalido ou expirado") from exc
    session = db.scalar(select(UserSession).where(UserSession.refresh_jti == token_id, UserSession.revoked_at.is_(None)))
    if not session or session.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sessao encerrada")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario inativo")
    session.revoked_at = datetime.now(timezone.utc)
    result = _issue_pair(user, db)
    return result


@router.post("/auth/logout", status_code=204)
def logout(data: RefreshRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        jti = payload.get("jti")
    except JWTError:
        jti = None
    if jti:
        session = db.scalar(select(UserSession).where(UserSession.refresh_jti == jti, UserSession.user_id == user.id))
        if session:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    return Response(status_code=204)


@router.get("/auth/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profiles = list(db.scalars(select(Profile.code).join(UserProfile).where(UserProfile.user_id == user.id)))
    return _user_payload(user, profiles)


@router.post("/auth/change-password", status_code=204)
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    user.password_hash = hash_password(data.new_password)
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).update({"revoked_at": datetime.now(timezone.utc)})
    db.commit()
    return Response(status_code=204)


@router.get("/usuarios")
def list_users(page: int = 1, page_size: int = 20, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    page_size = min(max(page_size, 1), 100)
    query = select(User).where(User.deleted_at.is_(None)).order_by(User.full_name).offset((page - 1) * page_size).limit(page_size)
    total = db.scalar(select(func.count(User.id)).where(User.deleted_at.is_(None))) or 0
    users = db.scalars(query).all()
    return {"items": [_user_payload(user, list(db.scalars(select(Profile.code).join(UserProfile).where(UserProfile.user_id == user.id)))) for user in users], "total": total, "page": page, "page_size": page_size}


@router.post("/usuarios", status_code=201)
def create_user(data: UserCreate, actor: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where((User.cpf == data.cpf) | (User.email == data.email))):
        raise HTTPException(status_code=409, detail="CPF ou e-mail ja cadastrado")
    profiles = list(db.scalars(select(Profile).where(Profile.code.in_(data.profile_codes))))
    if len(profiles) != len(set(data.profile_codes)):
        raise HTTPException(status_code=422, detail="Perfil inexistente")
    user = User(cpf=data.cpf, email=str(data.email).lower(), full_name=data.full_name, password_hash=hash_password(data.password), created_by=actor.id)
    db.add(user)
    db.flush()
    for profile in profiles:
        db.add(UserProfile(user_id=user.id, profile_id=profile.id))
    AuditService(db).record(actor.id, "usuarios", user.id, "criacao", after={"cpf": f"***{user.cpf[-4:]}", "profiles": data.profile_codes})
    db.commit()
    return _user_payload(user, data.profile_codes)


@router.get("/segurados")
def list_insured(page: int = 1, page_size: int = 20, tipo_vinculo: str | None = None, situacao: str | None = None, _: User = Depends(any_staff), db: Session = Depends(get_db)):
    if page < 1:
        raise HTTPException(status_code=422, detail="page deve ser maior que zero")
    page_size = min(max(page_size, 1), 100)
    rows, total = InsuredRepository(db).list(page, page_size, tipo_vinculo, situacao)
    items = [{"id": insured.id, "person_id": person.id, "cpf": _mask_cpf(person.cpf), "full_name": person.full_name, "birth_date": person.birth_date, "tipo_vinculo": insured.tipo_vinculo, "situacao": insured.situacao, "registration_number": insured.registration_number, "created_at": insured.created_at} for insured, person in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/segurados", status_code=201)
def create_insured(data: InsuredCreate, user: User = Depends(operator_or_admin), db: Session = Depends(get_db)):
    insured = InsuredService(db).create(data, user.id)
    person = db.get(Person, insured.person_id)
    return {"id": insured.id, "person_id": person.id, "cpf": _mask_cpf(person.cpf), "full_name": person.full_name, "tipo_vinculo": insured.tipo_vinculo, "situacao": insured.situacao, "registration_number": insured.registration_number}


@router.delete("/segurados/{insured_id}", status_code=204)
def delete_insured(insured_id: int, user: User = Depends(operator_or_admin), db: Session = Depends(get_db)):
    insured = db.get(Insured, insured_id)
    if not insured or insured.deleted_at:
        raise HTTPException(status_code=404, detail="Segurado nao encontrado")
    before = {"situacao": insured.situacao, "tipo_vinculo": insured.tipo_vinculo}
    insured.deleted_at = datetime.now(timezone.utc)
    AuditService(db).record(user.id, "segurados", insured.id, "exclusao_logica", before=before)
    db.commit()
    return Response(status_code=204)


@router.get("/tipos-documento")
def list_document_types(_: User = Depends(any_staff), db: Session = Depends(get_db)):
    return [{"id": item.id, "name": item.name, "required_for": item.required_for, "requires_expiry": item.requires_expiry, "accepted_mime_types": item.accepted_mime_types, "max_size_bytes": item.max_size_bytes} for item in db.scalars(select(DocumentType).where(DocumentType.deleted_at.is_(None)).order_by(DocumentType.name))]


@router.post("/tipos-documento", status_code=201)
def create_document_type(data: DocumentTypeCreate, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = DocumentType(**data.model_dump(), created_by=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    AuditService(db).record(user.id, "tipos_documento", item.id, "criacao", after={"name": item.name})
    db.commit()
    return {"id": item.id, **data.model_dump()}


@router.post("/documentos", status_code=201)
async def upload_document(insured_id: int, document_type_id: int, file: UploadFile = File(...), user: User = Depends(operator_or_admin), db: Session = Depends(get_db)):
    item = await DocumentService(db).upload(insured_id, document_type_id, file, user.id)
    return {"id": item.id, "insured_id": item.insured_id, "document_type_id": item.document_type_id, "status": item.status, "size_bytes": item.size_bytes, "created_at": item.created_at}


@router.get("/documentos")
def list_documents(status_filter: str | None = None, insured_id: int | None = None, _: User = Depends(any_staff), db: Session = Depends(get_db)):
    statement = select(Document).where(Document.deleted_at.is_(None))
    if status_filter:
        statement = statement.where(Document.status == status_filter)
    if insured_id:
        statement = statement.where(Document.insured_id == insured_id)
    return [{"id": item.id, "insured_id": item.insured_id, "document_type_id": item.document_type_id, "status": item.status, "validade": item.validade, "size_bytes": item.size_bytes} for item in db.scalars(statement.order_by(Document.created_at.desc()).limit(200))]


@router.patch("/documentos/{document_id}/analise")
def review_document(document_id: int, data: DocumentReview, user: User = Depends(operator_or_admin), db: Session = Depends(get_db)):
    item = db.get(Document, document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")
    if data.status == "rejeitado" and not data.rejection_reason:
        raise HTTPException(status_code=422, detail="Informe o motivo da rejeicao")
    before = {"status": item.status}
    item.status, item.rejection_reason = data.status, data.rejection_reason
    item.analyzed_by, item.analyzed_at = user.id, datetime.now(timezone.utc)
    AuditService(db).record(user.id, "documentos", item.id, "analise", before=before, after={"status": item.status, "motivo": item.rejection_reason})
    db.commit()
    return {"id": item.id, "status": item.status, "rejection_reason": item.rejection_reason}


@router.post("/campanhas", status_code=201)
def create_campaign(data: CampaignCreate, user: User = Depends(operator_or_admin), db: Session = Depends(get_db)):
    if data.end_date < data.start_date:
        raise HTTPException(status_code=422, detail="Periodo da campanha invalido")
    item = CensusCampaign(**data.model_dump(), created_by=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    AuditService(db).record(user.id, "campanhas_recenseamento", item.id, "criacao", after={"name": item.name})
    db.commit()
    return {"id": item.id, **data.model_dump(), "status": item.status}


@router.get("/campanhas")
def list_campaigns(_: User = Depends(any_staff), db: Session = Depends(get_db)):
    return [{"id": item.id, "name": item.name, "start_date": item.start_date, "end_date": item.end_date, "target_audience": item.target_audience, "status": item.status} for item in db.scalars(select(CensusCampaign).where(CensusCampaign.deleted_at.is_(None)).order_by(CensusCampaign.start_date.desc()))]


@router.post("/recenseamentos", status_code=201)
def create_census(data: CensusCreate, user: User = Depends(operator_or_admin), db: Session = Depends(get_db)):
    item = CensusService(db).register(data.insured_id, data.campaign_id, data.channel, data.status, user.id)
    return {"id": item.id, "insured_id": item.insured_id, "campaign_id": item.campaign_id, "data": item.data, "channel": item.channel, "status": item.status}


@router.get("/recenseamentos")
def list_census(campaign_id: int | None = None, status_filter: str | None = None, _: User = Depends(any_staff), db: Session = Depends(get_db)):
    statement = select(Census).where(Census.deleted_at.is_(None))
    if campaign_id:
        statement = statement.where(Census.campaign_id == campaign_id)
    if status_filter:
        statement = statement.where(Census.status == status_filter)
    return [{"id": item.id, "insured_id": item.insured_id, "campaign_id": item.campaign_id, "data": item.data, "channel": item.channel, "status": item.status, "risk_of_suspension": item.risk_of_suspension} for item in db.scalars(statement.order_by(Census.created_at.desc()).limit(500))]


@router.get("/monitoramento/acessos")
def access_monitoring(page: int = 1, page_size: int = 50, sucesso: bool | None = None, _: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    page_size = min(max(page_size, 1), 200)
    statement = select(AccessLog)
    count_statement = select(func.count(AccessLog.id))
    if sucesso is not None:
        statement = statement.where(AccessLog.sucesso == sucesso)
        count_statement = count_statement.where(AccessLog.sucesso == sucesso)
    total = db.scalar(count_statement) or 0
    items = db.scalars(statement.order_by(AccessLog.data_hora.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": item.id, "usuario_id": item.user_id, "ip": item.ip, "user_agent": item.user_agent, "sucesso": item.sucesso, "motivo": item.motivo, "data_hora": item.data_hora} for item in items], "total": total, "page": page, "page_size": page_size}


@router.get("/monitoramento/cadastros")
def registration_monitoring(_: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    by_type = dict(db.execute(select(Insured.tipo_vinculo, func.count()).where(Insured.deleted_at.is_(None)).group_by(Insured.tipo_vinculo)).all())
    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent = db.scalar(select(func.count(Insured.id)).where(Insured.created_at >= since, Insured.deleted_at.is_(None))) or 0
    pending_documents = db.scalar(select(func.count(Document.id)).where(Document.status.in_(["pendente", "em_analise"]), Document.deleted_at.is_(None))) or 0
    pending_census = db.scalar(select(func.count(Census.id)).where(Census.status == "pendente", Census.deleted_at.is_(None))) or 0
    return {"segurados_por_vinculo": by_type, "novos_ultimos_30_dias": recent, "documentos_pendentes": pending_documents, "recenseamentos_pendentes": pending_census}


@router.get("/dashboard")
def dashboard(_: User = Depends(any_staff), db: Session = Depends(get_db)):
    totals = dict(db.execute(select(Insured.tipo_vinculo, func.count()).where(Insured.deleted_at.is_(None)).group_by(Insured.tipo_vinculo)).all())
    total = sum(totals.values())
    census_total = db.scalar(select(func.count(Census.id))) or 0
    census_done = db.scalar(select(func.count(Census.id)).where(Census.status == "realizado")) or 0
    doc_pending = db.scalar(select(func.count(Document.id)).where(Document.status.in_(["pendente", "em_analise"]))) or 0
    today = datetime.now(timezone.utc).date()
    months = []
    year, month = today.year, today.month
    for _ in range(5):
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    first_month = datetime(year, month, 1, tzinfo=timezone.utc)
    for offset in range(6):
        month_index = first_month.month - 1 + offset
        month_year = first_month.year + month_index // 12
        month_number = month_index % 12 + 1
        months.append({"month": date(month_year, month_number, 1).strftime("%b"), "year": month_year, "month_number": month_number, "total": 0})
    period_rows = db.execute(select(func.extract("year", Insured.created_at), func.extract("month", Insured.created_at), func.count()).where(Insured.created_at >= first_month, Insured.deleted_at.is_(None)).group_by(func.extract("year", Insured.created_at), func.extract("month", Insured.created_at))).all()
    counts_by_month = {(int(row_year), int(row_month)): count for row_year, row_month, count in period_rows}
    for item in months:
        item["total"] = counts_by_month.get((item["year"], item["month_number"]), 0)
        del item["year"]
        del item["month_number"]
    recent_rows = db.execute(select(Insured, Person).join(Person, Person.id == Insured.person_id).where(Insured.deleted_at.is_(None)).order_by(Insured.created_at.desc()).limit(4)).all()
    recent = [{"id": insured.id, "name": person.full_name, "cpf": _mask_cpf(person.cpf), "type": insured.tipo_vinculo, "status": insured.situacao, "created_at": insured.created_at} for insured, person in recent_rows]
    return {"segurados_total": total, "segurados_por_vinculo": totals, "documentos_pendentes": doc_pending, "recenseamentos_total": census_total, "recenseamentos_realizados": census_done, "percentual_recenseamento": round(census_done * 100 / census_total, 1) if census_total else 0, "cadastros_por_mes": months, "recentes": recent}


@router.get("/auditoria")
def list_audit(page: int = 1, page_size: int = 50, entidade: str | None = None, _: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    page_size = min(max(page_size, 1), 200)
    statement = select(AuditLog)
    count_statement = select(func.count(AuditLog.id))
    if entidade:
        statement, count_statement = statement.where(AuditLog.entidade == entidade), count_statement.where(AuditLog.entidade == entidade)
    total = db.scalar(count_statement) or 0
    records = db.scalars(statement.order_by(AuditLog.data_hora.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": item.id, "usuario_id": item.user_id, "entidade": item.entidade, "entidade_id": item.entidade_id, "acao": item.acao, "dados_antes": item.dados_antes, "dados_depois": item.dados_depois, "data_hora": item.data_hora} for item in records], "total": total, "page": page, "page_size": page_size}


REPORT_NAMES = {
    "segurados_por_vinculo": "Segurados por vinculo",
    "beneficiarios_ativos": "Aposentados e pensionistas ativos",
    "recenseamento_campanha": "Recenseamento por campanha",
    "documentos_pendentes": "Documentos pendentes e vencidos",
    "cadastros_por_periodo": "Cadastros por periodo",
    "acessos_e_falhas": "Acessos e falhas de login",
    "auditoria": "Auditoria de alteracoes",
}


def _report_rows(db: Session, report_type: str, filters: dict):
    if report_type in ("segurados_por_vinculo", "beneficiarios_ativos", "cadastros_por_periodo"):
        statement = select(Insured, Person).join(Person, Person.id == Insured.person_id).where(Insured.deleted_at.is_(None))
        if report_type == "beneficiarios_ativos":
            statement = statement.where(Insured.tipo_vinculo.in_(["aposentado", "pensionista"]), Insured.situacao == "ativo")
        if filters.get("tipo_vinculo"):
            statement = statement.where(Insured.tipo_vinculo == filters["tipo_vinculo"])
        rows = db.execute(statement.order_by(Person.full_name)).all()
        return [{"nome": p.full_name, "cpf": _mask_cpf(p.cpf), "vinculo": i.tipo_vinculo, "situacao": i.situacao, "matricula": i.registration_number, "criado_em": i.created_at.isoformat()} for i, p in rows]
    if report_type == "recenseamento_campanha":
        return [{"campanha_id": c.campaign_id, "segurado_id": c.insured_id, "status": c.status, "canal": c.channel, "data": c.data.isoformat() if c.data else None} for c in db.scalars(select(Census).order_by(Census.campaign_id))]
    if report_type == "documentos_pendentes":
        records = db.scalars(select(Document).where(Document.status.in_(["pendente", "em_analise", "rejeitado"]))).all()
        return [{"documento_id": d.id, "segurado_id": d.insured_id, "tipo_id": d.document_type_id, "status": d.status, "validade": d.validade.isoformat() if d.validade else None} for d in records]
    if report_type == "acessos_e_falhas":
        records = db.scalars(select(AccessLog).order_by(AccessLog.data_hora.desc()).limit(10000)).all()
        return [{"usuario_id": a.user_id, "ip": a.ip, "sucesso": a.sucesso, "motivo": a.motivo, "data_hora": a.data_hora.isoformat()} for a in records]
    records = db.scalars(select(AuditLog).order_by(AuditLog.data_hora.desc()).limit(10000)).all()
    return [{"usuario_id": a.user_id, "entidade": a.entidade, "entidade_id": a.entidade_id, "acao": a.acao, "data_hora": a.data_hora.isoformat()} for a in records]


@router.post("/relatorios")
def generate_report(data: ReportRequest, user: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    rows = _report_rows(db, data.type, data.filters)
    if data.columns:
        rows = [{key: row.get(key) for key in data.columns if key in row} for row in rows]
    default_columns = {
        "segurados_por_vinculo": ["nome", "cpf", "vinculo", "situacao", "matricula", "criado_em"],
        "beneficiarios_ativos": ["nome", "cpf", "vinculo", "situacao", "matricula", "criado_em"],
        "cadastros_por_periodo": ["nome", "cpf", "vinculo", "situacao", "matricula", "criado_em"],
        "recenseamento_campanha": ["campanha_id", "segurado_id", "status", "canal", "data"],
        "documentos_pendentes": ["documento_id", "segurado_id", "tipo_id", "status", "validade"],
        "acessos_e_falhas": ["usuario_id", "ip", "sucesso", "motivo", "data_hora"],
        "auditoria": ["usuario_id", "entidade", "entidade_id", "acao", "data_hora"],
    }
    report = pd.DataFrame(rows, columns=(data.columns or default_columns[data.type]) if not rows else None)
    filename = f"{data.type}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    if data.format == "csv":
        content, media_type, extension = report.to_csv(index=False).encode("utf-8-sig"), "text/csv; charset=utf-8", "csv"
    elif data.format == "xlsx":
        stream = BytesIO()
        with pd.ExcelWriter(stream, engine="openpyxl") as writer:
            report.to_excel(writer, index=False, sheet_name="Relatorio")
        content, media_type, extension = stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        stream = BytesIO()
        document = SimpleDocTemplate(stream, pagesize=landscape(A4), title=REPORT_NAMES[data.type])
        table_rows = [list(report.columns)] + report.fillna("").astype(str).values.tolist()
        table = Table(table_rows, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#466a55")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9dfd8")), ("FONTSIZE", (0, 0), (-1, -1), 7), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f2")])]))
        document.build([table])
        content, media_type, extension = stream.getvalue(), "application/pdf", "pdf"
    record = {"type": data.type, "filters": data.filters, "format": data.format, "status": "concluido", "file_name": f"{filename}.{extension}", "requester_id": user.id}
    from app.models import GeneratedReport
    db.add(GeneratedReport(**record))
    db.commit()
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}.{extension}"'})


@router.get("/relatorios")
def report_history(_: User = Depends(auditor_or_admin), db: Session = Depends(get_db)):
    from app.models import GeneratedReport
    return [{"id": r.id, "type": r.type, "filters": r.filters, "format": r.format, "status": r.status, "file_name": r.file_name, "requester_id": r.requester_id, "created_at": r.created_at} for r in db.scalars(select(GeneratedReport).order_by(GeneratedReport.created_at.desc()).limit(100))]
