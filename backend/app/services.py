from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import ActiveEmployee, AuditLog, Census, CensusCampaign, Document, DocumentType, Insured, Person, Pensioner, Retiree, User, UserSession
from app.observability import append_business_event
from app.repositories import InsuredRepository
from app.schemas import InsuredCreate


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(self, user_id: int | None, entity: str, entity_id: int | str, action: str, before=None, after=None) -> None:
        self.db.add(AuditLog(user_id=user_id, entidade=entity, entidade_id=str(entity_id), acao=action, dados_antes=before, dados_depois=after))
        append_business_event(self.db, f"{entity}.{action}", entity, entity_id, user_id, {"before": before, "after": after})


class InsuredService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = InsuredRepository(db)

    def create(self, data: InsuredCreate, actor_id: int) -> Insured:
        values = data.model_dump()
        kind = values["tipo_vinculo"]
        if kind == "ativo" and not all(values.get(field) is not None for field in ("registration_number", "admission_date", "regime", "base_salary")):
            raise HTTPException(status_code=422, detail="Servidor ativo requer matricula, admissao, regime e salario base")
        if kind == "aposentado" and not all(values.get(field) is not None for field in ("registration_number", "retirement_type", "concession_date", "process_number", "benefit_amount")):
            raise HTTPException(status_code=422, detail="Aposentado requer matricula, tipo, concessao, processo e beneficio")
        if kind == "pensionista" and not all(values.get(field) is not None for field in ("institutor_id", "kinship", "death_date", "pension_type", "quota_percent", "pension_start_date")):
            raise HTTPException(status_code=422, detail="Pensionista requer instituidor, parentesco, obito, tipo, cota e inicio")
        if kind == "pensionista":
            institutor = self.db.get(Insured, values["institutor_id"])
            if not institutor or institutor.tipo_vinculo not in ("ativo", "aposentado"):
                raise HTTPException(status_code=422, detail="Instituidor deve ser um segurado existente")
        if self.db.scalar(select(Person.id).where(Person.cpf == values["cpf"], Person.deleted_at.is_(None))):
            raise HTTPException(status_code=409, detail="Ja existe pessoa ativa com este CPF")
        person_keys = ("cpf", "full_name", "birth_date", "email", "social_name", "gender", "marital_status", "mother_name")
        person = Person(**{key: values[key] for key in person_keys}, created_by=actor_id)
        self.db.add(person)
        self.db.flush()
        insured = Insured(person_id=person.id, tipo_vinculo=kind, situacao=values["situacao"], registration_number=values["registration_number"], admission_date=values["admission_date"], termination_date=values["termination_date"], created_by=actor_id)
        self.db.add(insured)
        self.db.flush()
        if kind == "ativo":
            self.db.add(ActiveEmployee(insured_id=insured.id, organization_id=values["organization_id"], position_id=values["position_id"], regime=values["regime"], base_salary=values["base_salary"]))
        elif kind == "aposentado":
            self.db.add(Retiree(insured_id=insured.id, retirement_type=values["retirement_type"], concession_date=values["concession_date"], process_number=values["process_number"], benefit_amount=values["benefit_amount"]))
        else:
            self.db.add(Pensioner(insured_id=insured.id, institutor_id=values["institutor_id"], kinship=values["kinship"], death_date=values["death_date"], pension_type=values["pension_type"], quota_percent=values["quota_percent"], start_date=values["pension_start_date"], end_date=values["pension_end_date"]))
        AuditService(self.db).record(actor_id, "segurados", insured.id, "criacao", after={"tipo_vinculo": kind, "cpf": f"***{values['cpf'][-4:]}", "situacao": insured.situacao})
        self.db.commit()
        self.db.refresh(insured)
        return insured


class DocumentService:
    allowed_mimes = {"application/pdf", "image/jpeg", "image/png"}

    def __init__(self, db: Session):
        self.db = db

    async def upload(self, insured_id: int, document_type_id: int, upload: UploadFile, actor_id: int) -> Document:
        insured = self.db.get(Insured, insured_id)
        document_type = self.db.get(DocumentType, document_type_id)
        if not insured or not document_type:
            raise HTTPException(status_code=404, detail="Segurado ou tipo de documento nao encontrado")
        if upload.content_type not in self.allowed_mimes or upload.content_type not in document_type.accepted_mime_types:
            raise HTTPException(status_code=415, detail="Formato de arquivo nao permitido")
        content = await upload.read(settings.max_upload_bytes + 1)
        if len(content) > min(settings.max_upload_bytes, document_type.max_size_bytes):
            raise HTTPException(status_code=413, detail="Arquivo excede o limite permitido")
        if not self._matches_signature(content, upload.content_type):
            raise HTTPException(status_code=415, detail="Conteudo nao corresponde ao tipo declarado")
        safe_suffix = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}[upload.content_type]
        stored_name = f"{uuid4().hex}{safe_suffix}"
        destination = Path(settings.upload_dir)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / stored_name).write_bytes(content)
        document = Document(insured_id=insured_id, document_type_id=document_type_id, stored_name=stored_name, original_name=Path(upload.filename or "documento").name[:255], mime_type=upload.content_type, size_bytes=len(content), status="pendente", created_by=actor_id)
        self.db.add(document)
        AuditService(self.db).record(actor_id, "documentos", stored_name, "criacao", after={"tipo": document_type.name, "status": "pendente"})
        self.db.commit()
        self.db.refresh(document)
        return document

    @staticmethod
    def _matches_signature(content: bytes, mime: str) -> bool:
        return (mime == "application/pdf" and content.startswith(b"%PDF-")) or (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or (mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))


class CensusService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, insured_id: int, campaign_id: int, channel: str, census_status: str, actor_id: int) -> Census:
        insured = self.db.get(Insured, insured_id)
        campaign = self.db.get(CensusCampaign, campaign_id)
        if not insured or not campaign:
            raise HTTPException(status_code=404, detail="Segurado ou campanha nao encontrado")
        if insured.tipo_vinculo not in campaign.target_audience:
            raise HTTPException(status_code=422, detail="Vinculo fora do publico-alvo da campanha")
        if self.db.scalar(select(Census.id).where(Census.insured_id == insured_id, Census.campaign_id == campaign_id)):
            raise HTTPException(status_code=409, detail="Segurado ja possui registro nesta campanha")
        now = datetime.now(timezone.utc)
        result = Census(insured_id=insured_id, campaign_id=campaign_id, channel=channel, status=census_status, data=now if census_status == "realizado" else None, responsible_id=actor_id, risk_of_suspension=False)
        self.db.add(result)
        AuditService(self.db).record(actor_id, "recenseamentos", insured_id, "criacao", after={"campanha_id": campaign_id, "status": census_status})
        self.db.commit()
        self.db.refresh(result)
        return result


def password_expiry(session: UserSession) -> datetime:
    return session.expires_at
