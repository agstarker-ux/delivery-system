"""
Rotas WebSocket para GPS em tempo real.

Endpoints:
  ws://.../ws/motoboy/{motoboy_id}?token=...   -> motoboy envia posição
  ws://.../ws/admin?token=...                   -> admin recebe tudo
  ws://.../ws/cliente/{pedido_id}?token=...     -> cliente recebe do seu pedido
"""
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decodificar_token
from app.database import AsyncSessionLocal
from app.models import Motoboy, Usuario, PosicaoGPS
from app.schemas import PosicaoGPSInput
from app.websocket_manager import gerenciador

logger = logging.getLogger("websocket_gps")
router = APIRouter(tags=["WebSocket GPS"])


async def _autenticar_websocket(token: str) -> dict | None:
    """Valida o JWT recebido via query param. WebSocket não usa headers Authorization padrão."""
    try:
        return decodificar_token(token)
    except Exception:
        return None


@router.websocket("/ws/motoboy/{motoboy_id}")
async def websocket_motoboy(websocket: WebSocket, motoboy_id: str, token: str = Query(...)):
    """
    O app do motoboy conecta aqui e envia, periodicamente (ex: a cada 3-5s),
    um JSON no formato de PosicaoGPSInput:
        {"latitude": -3.2997, "longitude": -60.6206, "velocidade": 32.5, "pedido_id": "uuid-ou-null"}
    """
    payload = await _autenticar_websocket(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
        return

    # Confirma que o motoboy_id da URL pertence de fato ao usuário do token
    # (exceto se for admin, que pode monitorar/testar qualquer motoboy).
    async with AsyncSessionLocal() as db:
        resultado = await db.execute(select(Motoboy).where(Motoboy.id == motoboy_id))
        motoboy = resultado.scalar_one_or_none()
        if motoboy is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Motoboy não encontrado")
            return

        usuario_do_token = payload.get("sub")
        tipo_do_token = payload.get("tipo")
        if tipo_do_token != "admin" and motoboy.usuario_id != usuario_do_token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token não pertence a este motoboy")
            return

    await gerenciador.conectar_motoboy(motoboy_id, websocket)

    try:

        while True:
            dados_brutos = await websocket.receive_json()
            try:
                posicao = PosicaoGPSInput(**dados_brutos)
            except Exception as e:
                await websocket.send_json({"erro": f"Payload inválido: {e}"})
                continue

            agora = datetime.utcnow()

            # Atualiza a posição "atual" do motoboy (leitura rápida) e grava histórico
            async with AsyncSessionLocal() as db:
                resultado = await db.execute(select(Motoboy).where(Motoboy.id == motoboy_id))
                motoboy = resultado.scalar_one_or_none()
                if motoboy:
                    motoboy.latitude_atual = posicao.latitude
                    motoboy.longitude_atual = posicao.longitude
                    motoboy.atualizado_em = agora

                    db.add(PosicaoGPS(
                        motoboy_id=motoboy_id,
                        pedido_id=posicao.pedido_id,
                        latitude=posicao.latitude,
                        longitude=posicao.longitude,
                        velocidade=posicao.velocidade,
                        precisao=posicao.precisao,
                        registrado_em=agora,
                    ))
                    await db.commit()

            # Repassa em tempo real para admins e cliente do pedido
            await gerenciador.broadcast_posicao(
                motoboy_id=motoboy_id,
                latitude=posicao.latitude,
                longitude=posicao.longitude,
                velocidade=posicao.velocidade,
                pedido_id=posicao.pedido_id,
            )

            # Confirmação leve para o motoboy (opcional, ajuda a debugar no app)
            await websocket.send_json({"status": "ok", "recebido_em": agora.isoformat()})

    except WebSocketDisconnect:
        logger.info(f"Motoboy {motoboy_id} desconectou")
    finally:
        gerenciador.desconectar_motoboy(motoboy_id)
        # Marca offline no banco
        async with AsyncSessionLocal() as db:
            resultado = await db.execute(select(Motoboy).where(Motoboy.id == motoboy_id))
            motoboy = resultado.scalar_one_or_none()
            if motoboy:
                from app.models import StatusMotoboy
                motoboy.status = StatusMotoboy.OFFLINE
                await db.commit()
        await gerenciador.notificar_admins("motoboy_offline", {"motoboy_id": motoboy_id})


@router.websocket("/ws/admin")
async def websocket_admin(websocket: WebSocket, token: str = Query(...)):
    """Painel admin conecta aqui e recebe a posição de TODOS os motoboys em tempo real."""
    payload = await _autenticar_websocket(token)
    if payload is None or payload.get("tipo") != "admin":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Acesso restrito a administradores")
        return

    await gerenciador.conectar_admin(websocket)
    try:
        while True:
            # Mantém a conexão viva; admin normalmente só recebe, não envia.
            # Se o cliente mandar algo (ex: ping), apenas ignoramos/logamos.
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Admin desconectou do painel ao vivo")
    finally:
        gerenciador.desconectar_admin(websocket)


@router.websocket("/ws/cliente/{pedido_id}")
async def websocket_cliente(websocket: WebSocket, pedido_id: str, token: str = Query(...)):
    """Cliente conecta aqui para acompanhar, ao vivo, o motoboy do SEU pedido específico."""
    payload = await _autenticar_websocket(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
        return

    # TODO produção: validar que pedido_id realmente pertence ao usuário do token
    await gerenciador.conectar_cliente(pedido_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Cliente desconectou do acompanhamento do pedido {pedido_id}")
    finally:
        gerenciador.desconectar_cliente(pedido_id, websocket)
