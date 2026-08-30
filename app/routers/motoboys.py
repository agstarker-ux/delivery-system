from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import exigir_tipo, obter_usuario_atual
from app.database import get_db
from app.models import Motoboy, Usuario
from app.schemas import MotoboyResponse, AtualizacaoStatusMotoboy
from app.websocket_manager import gerenciador

router = APIRouter(prefix="/motoboys", tags=["Motoboys"])


@router.get("/", response_model=list[MotoboyResponse])
async def listar_motoboys(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(exigir_tipo("admin")),
):
    resultado = await db.execute(select(Motoboy))
    return resultado.scalars().all()


@router.get("/me", response_model=MotoboyResponse)
async def meu_perfil_motoboy(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("motoboy")),
):
    resultado = await db.execute(select(Motoboy).where(Motoboy.usuario_id == usuario.id))
    motoboy = resultado.scalar_one_or_none()
    if motoboy is None:
        raise HTTPException(status_code=404, detail="Perfil de motoboy não encontrado")
    return motoboy


@router.patch("/me/status", response_model=MotoboyResponse)
async def atualizar_status(
    dados: AtualizacaoStatusMotoboy,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("motoboy")),
):
    resultado = await db.execute(select(Motoboy).where(Motoboy.usuario_id == usuario.id))
    motoboy = resultado.scalar_one_or_none()
    if motoboy is None:
        raise HTTPException(status_code=404, detail="Perfil de motoboy não encontrado")

    motoboy.status = dados.status
    await db.commit()
    await db.refresh(motoboy)

    await gerenciador.notificar_admins(
        "motoboy_status_alterado",
        {"motoboy_id": motoboy.id, "status": motoboy.status.value},
    )
    return motoboy
