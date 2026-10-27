from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import User, UserProfile, Profile


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        user_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas", headers={"WWW-Authenticate": "Bearer"}) from exc
    user = db.get(User, user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inativo")
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        codes = db.scalars(select(Profile.code).join(UserProfile).where(UserProfile.user_id == user.id)).all()
        if not set(codes).intersection(roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil sem permissao para esta operacao")
        return user
    return dependency


operator_or_admin = require_roles("administrador", "operador")
auditor_or_admin = require_roles("administrador", "auditor")
admin_only = require_roles("administrador")
super_admin_only = require_roles("super_administrador")
any_staff = require_roles("administrador", "operador", "auditor")
