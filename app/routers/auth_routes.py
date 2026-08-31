from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_senha, verificar_senha, criar_access_token
from app.database import get_db
from app.models import Usuario, Cliente, Motoboy
from app.rate_limit import limitar_por_ip
from app.schemas import RegistroUsuario, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/registrar",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limitar_por_ip(max_tentativas=5, janela_segundos=300))],
)
async def registrar(dados: RegistroUsuario, db: AsyncSession = Depends(get_db)):
    resultado = await db.execute(select(Usuario).where(Usuario.telefone == dados.telefone))
    if resultado.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Telefone já cadastrado")

    usuario = Usuario(
        nome=dados.nome,
        telefone=dados.telefone,
        senha_hash=hash_senha(dados.senha),
        tipo=dados.tipo,
    )
    db.add(usuario)
    await db.flush()

    if dados.tipo == "cliente":
        db.add(Cliente(usuario_id=usuario.id))
    else:
        db.add(Motoboy(usuario_id=usuario.id))

    await db.commit()

    token = criar_access_token({"sub": usuario.id, "tipo": usuario.tipo})
    return TokenResponse(access_token=token, usuario_id=usuario.id, tipo=usuario.tipo, nome=usuario.nome)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(limitar_por_ip(max_tentativas=10, janela_segundos=300))],
)
async def login(dados: LoginRequest, db: AsyncSession = Depends(get_db)):
    resultado = await db.execute(select(Usuario).where(Usuario.telefone == dados.telefone))
    usuario = resultado.scalar_one_or_none()

    if usuario is None or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Telefone ou senha incorretos")

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada")

    token = criar_access_token({"sub": usuario.id, "tipo": usuario.tipo})
    return TokenResponse(access_token=token, usuario_id=usuario.id, tipo=usuario.tipo, nome=usuario.nome)
