from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import exigir_tipo
from app.database import get_db
from app.geofence import validar_dentro_da_area_piloto
from app.models import Endereco, Cliente, Pedido, Usuario
from app.schemas import EnderecoCreate, EnderecoResponse

router = APIRouter(prefix="/enderecos", tags=["Endereços"])


@router.post("/", response_model=EnderecoResponse, status_code=201)
async def cadastrar_endereco(
    dados: EnderecoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("cliente")),
):
    validar_dentro_da_area_piloto(dados.latitude, dados.longitude, contexto="endereço de entrega")

    resultado = await db.execute(select(Cliente).where(Cliente.usuario_id == usuario.id))
    cliente = resultado.scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Perfil de cliente não encontrado")

    endereco = Endereco(cliente_id=cliente.id, **dados.model_dump())
    db.add(endereco)
    await db.commit()
    await db.refresh(endereco)
    return endereco


@router.get("/", response_model=list[EnderecoResponse])
async def listar_meus_enderecos(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("cliente")),
):
    resultado = await db.execute(select(Cliente).where(Cliente.usuario_id == usuario.id))
    cliente = resultado.scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Perfil de cliente não encontrado")

    resultado = await db.execute(select(Endereco).where(Endereco.cliente_id == cliente.id))
    return resultado.scalars().all()


@router.delete("/{endereco_id}", status_code=204)
async def remover_endereco(
    endereco_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("cliente")),
):
    resultado = await db.execute(select(Cliente).where(Cliente.usuario_id == usuario.id))
    cliente = resultado.scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Perfil de cliente não encontrado")

    resultado = await db.execute(
        select(Endereco).where(Endereco.id == endereco_id, Endereco.cliente_id == cliente.id)
    )
    endereco = resultado.scalar_one_or_none()
    if endereco is None:
        raise HTTPException(status_code=404, detail="Endereço não encontrado ou não pertence a você")

    resultado_pedidos = await db.execute(
        select(Pedido.id).where(Pedido.endereco_id == endereco.id).limit(1)
    )
    if resultado_pedidos.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este endereço já está ligado a um pedido e não pode ser removido.",
        )

    await db.delete(endereco)
    await db.commit()
