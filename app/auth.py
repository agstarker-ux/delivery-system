from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_senha(senha_pura: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_pura.encode("utf-8"), salt).decode("utf-8")


def verificar_senha(senha_pura: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha_pura.encode("utf-8"), senha_hash.encode("utf-8"))


def criar_access_token(dados: dict) -> str:
    payload = dados.copy()
    expira_em = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expira_em})
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def obter_usuario_atual(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    payload = decodificar_token(token)
    usuario_id: str | None = payload.get("sub")
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Token sem identificação de usuário")

    resultado = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario = resultado.scalar_one_or_none()
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Usuário não encontrado ou inativo")

    return usuario


def exigir_tipo(*tipos_permitidos: str):
    async def verificador(usuario: Usuario = Depends(obter_usuario_atual)) -> Usuario:
        if usuario.tipo not in tipos_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso restrito a: {', '.join(tipos_permitidos)}",
            )
        return usuario
    return verificador
