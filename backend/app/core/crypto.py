from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def encrypt_sensitive(value: str) -> str:
    if not settings.bank_encryption_key:
        raise RuntimeError("BANK_ENCRYPTION_KEY nao configurada")
    return Fernet(settings.bank_encryption_key.encode()).encrypt(value.encode()).decode()


def decrypt_sensitive(value: str) -> str:
    if not settings.bank_encryption_key:
        raise RuntimeError("BANK_ENCRYPTION_KEY nao configurada")
    try:
        return Fernet(settings.bank_encryption_key.encode()).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Nao foi possivel descriptografar o dado") from exc
