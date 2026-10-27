from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import DocumentType, Permission, Profile, ProfilePermission, User, UserProfile


PROFILE_DEFINITIONS = {
    "administrador": ("Administrador", "Acesso administrativo completo"),
    "super_administrador": ("Super Administrador", "Governanca global e aprovacao de alteracoes sensiveis"),
    "operador": ("Operador/Atendente", "Cadastro, documentos e recenseamento"),
    "auditor": ("Auditor/Gestor", "Consulta, monitoramento e relatorios"),
    "segurado": ("Segurado", "Acesso a propria area, quando habilitada"),
}

PERMISSIONS = {
    "users:manage": "Gerenciar usuarios e perfis",
    "insured:read": "Consultar segurados",
    "insured:write": "Criar e editar segurados",
    "documents:review": "Analisar documentos",
    "census:manage": "Gerenciar recenseamento",
    "reports:read": "Consultar e gerar relatorios",
    "audit:read": "Consultar auditoria e acessos",
}

DOCUMENT_TYPES = [
    ("Documento de identidade", ["ativo", "aposentado", "pensionista"], False),
    ("CPF", ["ativo", "aposentado", "pensionista"], False),
    ("Comprovante de residencia", ["ativo", "aposentado", "pensionista"], True),
    ("Certidao de nascimento ou casamento", ["ativo", "aposentado", "pensionista"], False),
    ("Termo de posse", ["ativo"], False),
    ("Portaria de aposentadoria", ["aposentado"], False),
    ("Comprovante de vida", ["aposentado", "pensionista"], True),
]


def seed() -> None:
    with SessionLocal() as db:
        profiles = {}
        for code, (name, description) in PROFILE_DEFINITIONS.items():
            profile = db.scalar(select(Profile).where(Profile.code == code))
            if not profile:
                profile = Profile(code=code, name=name, description=description)
                db.add(profile)
                db.flush()
            profiles[code] = profile
        permissions = {}
        for code, description in PERMISSIONS.items():
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if not permission:
                permission = Permission(code=code, description=description)
                db.add(permission)
                db.flush()
            permissions[code] = permission
        for profile in profiles.values():
            for permission in permissions.values():
                exists = db.get(ProfilePermission, (profile.id, permission.id))
                if not exists:
                    db.add(ProfilePermission(profile_id=profile.id, permission_id=permission.id))
        for name, required_for, requires_expiry in DOCUMENT_TYPES:
            if not db.scalar(select(DocumentType.id).where(DocumentType.name == name)):
                db.add(DocumentType(name=name, required_for=required_for, requires_expiry=requires_expiry, accepted_mime_types=["application/pdf", "image/jpeg", "image/png"], max_size_bytes=settings.max_upload_bytes))
        admin = db.scalar(select(User).where(User.cpf == settings.admin_cpf))
        if not admin:
            admin = User(cpf=settings.admin_cpf, email=settings.admin_email, full_name="Administrador inicial", password_hash=hash_password(settings.admin_password))
            db.add(admin)
            db.flush()
        if not db.get(UserProfile, (admin.id, profiles["administrador"].id)):
            db.add(UserProfile(user_id=admin.id, profile_id=profiles["administrador"].id))
        if not db.get(UserProfile, (admin.id, profiles["super_administrador"].id)):
            db.add(UserProfile(user_id=admin.id, profile_id=profiles["super_administrador"].id))
        db.commit()


if __name__ == "__main__":
    seed()
    print("Seed aplicado")
