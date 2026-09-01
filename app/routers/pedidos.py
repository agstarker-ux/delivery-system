from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import exigir_tipo, obter_usuario_atual
from app.database import get_db
from app.geofence import validar_dentro_da_area_piloto
from app.models import Pedido, Cliente, Motoboy, Usuario, Endereco, StatusPedido, StatusMotoboy, transicao_e_valida
from app.schemas import PedidoCreate, PedidoResponse, PedidoStatusUpdate
from app.websocket_manager import gerenciador

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.post("/", response_model=PedidoResponse, status_code=201)
async def criar_pedido(
    dados: PedidoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("cliente")),
):
    resultado = await db.execute(select(Cliente).where(Cliente.usuario_id == usuario.id))
    cliente = resultado.scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Perfil de cliente não encontrado")

    resultado = await db.execute(
        select(Endereco).where(Endereco.id == dados.endereco_id, Endereco.cliente_id == cliente.id)
    )
    endereco = resultado.scalar_one_or_none()
    if endereco is None:
        raise HTTPException(
            status_code=404,
            detail="Endereço não encontrado ou não pertence a este cliente",
        )

    validar_dentro_da_area_piloto(
        dados.origem_latitude, dados.origem_longitude, contexto="estabelecimento de origem"
    )

    pedido = Pedido(
        cliente_id=cliente.id,
        endereco_id=dados.endereco_id,
        origem_nome=dados.origem_nome,
        origem_latitude=dados.origem_latitude,
        origem_longitude=dados.origem_longitude,
        itens_descricao=dados.itens_descricao,
        valor_total=dados.valor_total,
        taxa_entrega=dados.taxa_entrega,
        observacoes=dados.observacoes,
        status=StatusPedido.PENDENTE,
    )
    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)

    await gerenciador.notificar_admins("novo_pedido", {"pedido_id": pedido.id, "cliente_id": cliente.id})

    return pedido


@router.get("/", response_model=list[PedidoResponse])
async def listar_pedidos(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(exigir_tipo("admin")),
):
    resultado = await db.execute(select(Pedido).order_by(Pedido.criado_em.desc()))
    return resultado.scalars().all()


@router.get("/pendentes", response_model=list[PedidoResponse])
async def listar_pedidos_pendentes(
    db: AsyncSession = Depends(get_db),
    _motoboy: Usuario = Depends(exigir_tipo("motoboy", "admin")),
):
    resultado = await db.execute(
        select(Pedido).where(Pedido.status == StatusPedido.PENDENTE).order_by(Pedido.criado_em.asc())
    )
    return resultado.scalars().all()


@router.post("/{pedido_id}/aceitar", response_model=PedidoResponse)
async def aceitar_pedido(
    pedido_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("motoboy")),
):
    resultado = await db.execute(select(Motoboy).where(Motoboy.usuario_id == usuario.id))
    motoboy = resultado.scalar_one_or_none()
    if motoboy is None:
        raise HTTPException(status_code=404, detail="Perfil de motoboy não encontrado")

    if motoboy.status != StatusMotoboy.DISPONIVEL:
        raise HTTPException(
            status_code=409,
            detail="Fique disponível antes de aceitar um pedido.",
        )

    # Bloqueia o pedido dentro da transação para impedir dois aceites simultâneos.
    resultado = await db.execute(
        select(Pedido).where(Pedido.id == pedido_id).with_for_update()
    )
    pedido = resultado.scalar_one_or_none()
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if pedido.status != StatusPedido.PENDENTE:
        raise HTTPException(status_code=409, detail="Pedido já foi aceito ou não está mais disponível")

    pedido.motoboy_id = motoboy.id
    pedido.status = StatusPedido.ACEITO
    pedido.aceito_em = datetime.utcnow()
    motoboy.status = StatusMotoboy.EM_ENTREGA

    await db.commit()
    await db.refresh(pedido)

    gerenciador.vincular_pedido_a_motoboy(pedido_id, motoboy.id)
    await gerenciador.notificar_admins(
        "pedido_aceito", {"pedido_id": pedido.id, "motoboy_id": motoboy.id}
    )

    return pedido


@router.patch("/{pedido_id}/status", response_model=PedidoResponse)
async def atualizar_status_pedido(
    pedido_id: str,
    dados: PedidoStatusUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(exigir_tipo("motoboy", "admin")),
):
    resultado = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = resultado.scalar_one_or_none()
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if usuario.tipo == "motoboy":
        resultado_mb = await db.execute(select(Motoboy).where(Motoboy.usuario_id == usuario.id))
        motoboy = resultado_mb.scalar_one_or_none()
        if motoboy is None or pedido.motoboy_id != motoboy.id:
            raise HTTPException(status_code=403, detail="Este pedido não pertence a você")

    if not transicao_e_valida(pedido.status, dados.status):
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: não é possível ir de '{pedido.status.value}' para '{dados.status.value}'",
        )

    pedido.status = dados.status
    if dados.status in {StatusPedido.ENTREGUE, StatusPedido.CANCELADO}:
        if dados.status == StatusPedido.ENTREGUE:
            pedido.entregue_em = datetime.utcnow()

        if pedido.motoboy_id:
            resultado_mb = await db.execute(
                select(Motoboy).where(Motoboy.id == pedido.motoboy_id)
            )
            motoboy = resultado_mb.scalar_one_or_none()
            if motoboy and motoboy.status == StatusMotoboy.EM_ENTREGA:
                motoboy.status = StatusMotoboy.DISPONIVEL

        gerenciador.desvincular_pedido(pedido_id)

    await db.commit()
    await db.refresh(pedido)

    await gerenciador.notificar_admins(
        "pedido_status_alterado", {"pedido_id": pedido.id, "status": pedido.status.value}
    )
    return pedido


@router.get("/me/atual", response_model=PedidoResponse | None)
async def obter_pedido_atual(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    estados_ativos = {
        StatusPedido.PENDENTE,
        StatusPedido.ACEITO,
        StatusPedido.A_CAMINHO_COLETA,
        StatusPedido.COLETADO,
        StatusPedido.A_CAMINHO_ENTREGA,
    }

    if usuario.tipo == "cliente":
        resultado_perfil = await db.execute(
            select(Cliente).where(Cliente.usuario_id == usuario.id)
        )
        cliente = resultado_perfil.scalar_one_or_none()
        if cliente is None:
            raise HTTPException(status_code=404, detail="Perfil de cliente não encontrado")
        filtro = Pedido.cliente_id == cliente.id
    elif usuario.tipo == "motoboy":
        resultado_perfil = await db.execute(
            select(Motoboy).where(Motoboy.usuario_id == usuario.id)
        )
        motoboy = resultado_perfil.scalar_one_or_none()
        if motoboy is None:
            raise HTTPException(status_code=404, detail="Perfil de motoboy não encontrado")
        filtro = Pedido.motoboy_id == motoboy.id
    else:
        return None

    resultado = await db.execute(
        select(Pedido)
        .where(filtro, Pedido.status.in_(estados_ativos))
        .order_by(Pedido.criado_em.desc())
        .limit(1)
    )
    return resultado.scalar_one_or_none()


@router.get("/{pedido_id}", response_model=PedidoResponse)
async def obter_pedido(
    pedido_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    resultado = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = resultado.scalar_one_or_none()
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if usuario.tipo == "cliente":
        resultado_cli = await db.execute(select(Cliente).where(Cliente.usuario_id == usuario.id))
        cliente = resultado_cli.scalar_one_or_none()
        if cliente is None or pedido.cliente_id != cliente.id:
            raise HTTPException(status_code=403, detail="Este pedido não pertence a você")
    elif usuario.tipo == "motoboy":
        resultado_mb = await db.execute(select(Motoboy).where(Motoboy.usuario_id == usuario.id))
        motoboy = resultado_mb.scalar_one_or_none()
        if motoboy is None or pedido.motoboy_id != motoboy.id:
            raise HTTPException(status_code=403, detail="Este pedido não pertence a você")

    return pedido
