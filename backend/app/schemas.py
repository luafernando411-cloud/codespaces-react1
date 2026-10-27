import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def normalize_cpf(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11 or len(set(digits)) == 1:
        raise ValueError("CPF invalido")
    for position in (9, 10):
        total = sum(int(digits[index]) * (position + 1 - index) for index in range(position))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != int(digits[position]):
            raise ValueError("CPF invalido")
    return digits


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    cpf: str
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    profile_codes: list[str] = Field(default_factory=lambda: ["operador"])

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        return normalize_cpf(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not (re.search(r"[a-z]", value) and re.search(r"[A-Z]", value) and re.search(r"\d", value) and re.search(r"[^A-Za-z0-9]", value)):
            raise ValueError("A senha deve conter maiuscula, minuscula, numero e caractere especial")
        return value


class UserRead(ORMModel):
    id: int
    cpf: str
    email: EmailStr
    full_name: str
    is_active: bool
    profiles: list[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    cpf: str
    password: str

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        return normalize_cpf(value)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not (re.search(r"[a-z]", value) and re.search(r"[A-Z]", value) and re.search(r"\d", value) and re.search(r"[^A-Za-z0-9]", value)):
            raise ValueError("A senha deve conter maiuscula, minuscula, numero e caractere especial")
        return value


class PersonFields(BaseModel):
    cpf: str
    full_name: str = Field(min_length=3, max_length=160)
    birth_date: date
    email: EmailStr | None = None
    social_name: str | None = None
    gender: str | None = None
    marital_status: str | None = None
    mother_name: str | None = None

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        return normalize_cpf(value)


class InsuredCreate(PersonFields):
    tipo_vinculo: Literal["ativo", "aposentado", "pensionista"]
    situacao: str = "ativo"
    registration_number: str | None = Field(default=None, max_length=40)
    admission_date: date | None = None
    termination_date: date | None = None
    organization_id: int | None = None
    position_id: int | None = None
    regime: str | None = None
    base_salary: Decimal | None = Field(default=None, ge=0)
    retirement_type: str | None = None
    concession_date: date | None = None
    process_number: str | None = None
    benefit_amount: Decimal | None = Field(default=None, ge=0)
    institutor_id: int | None = None
    kinship: str | None = None
    death_date: date | None = None
    pension_type: str | None = None
    quota_percent: Decimal | None = Field(default=None, gt=0, le=100)
    pension_start_date: date | None = None
    pension_end_date: date | None = None


class InsuredRead(ORMModel):
    id: int
    person_id: int
    tipo_vinculo: str
    situacao: str
    registration_number: str | None
    created_at: datetime
    person: dict[str, Any] | None = None


class DocumentTypeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    required_for: list[str] = Field(default_factory=list)
    requires_expiry: bool = False
    accepted_mime_types: list[str] = Field(default_factory=lambda: ["application/pdf", "image/jpeg", "image/png"])
    max_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)


class DocumentReview(BaseModel):
    status: Literal["aprovado", "rejeitado"]
    rejection_reason: str | None = Field(default=None, max_length=500)


class CampaignCreate(BaseModel):
    name: str = Field(min_length=3, max_length=140)
    start_date: date
    end_date: date
    target_audience: list[Literal["aposentado", "pensionista"]]


class CensusCreate(BaseModel):
    insured_id: int
    campaign_id: int
    channel: Literal["presencial", "online"]
    status: Literal["realizado", "isento"] = "realizado"


class ReportRequest(BaseModel):
    type: Literal["segurados_por_vinculo", "beneficiarios_ativos", "recenseamento_campanha", "documentos_pendentes", "cadastros_por_periodo", "acessos_e_falhas", "auditoria"]
    format: Literal["csv", "xlsx", "pdf"]
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    group_by: str | None = None


class Page(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    status: str
    database: str
