import logging
import time
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.geofence import esta_na_area_piloto
from app.models import Motoboy, Usuario, PosicaoGPS, Pedido, Cliente
from app.schemas import PosicaoGPSInput
from app.websocket_manager import gerenciador
from app.ws_tokens import validar_token_ws

logger = logging.getLogger("websocket_gps")
router = APIRouter(tags=["WebSocket GPS"])


async def _autenticar_websocket(token: str) -> dict | None:
    usuario_id = validar_token_ws(token)
    if usuario_id is None:
        return None
    async with AsyncSessionLocal() as db:
        resultado = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
        usuario = resultado.scalar_one_or_none()
        if usuario is None or not usuario.ativo:
            return None
        return {"sub": usuario.id, "tipo": usuario.tipo}


@router.websocket("/ws/motoboy/{motoboy_id}")
async def websocket_motoboy(websocket: WebSocket, motoboy_id: str, token: str = Query(...)):
    payload = await _autenticar_websocket(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
        return

    async with AsyncSessionLocal() as db:
        resultado = await db.execute(select(Motoboy).where(Motoboy.id == motoboy_id))
        motoboy = resultado.scalar_one_or_none()
        if motoboy is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Motoboy não encontrado")
            return

        usuario_do_token = payload.get("sub")
        tipo_do_token = payload.get("tipo")
        if tipo_do_token != "motoboy" or motoboy.usuario_id != usuario_do_token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Apenas o próprio motoboy pode enviar GPS")
            return

    await gerenciador.conectar_motoboy(motoboy_id, websocket)

    ultimo_envio = 0.0
    intervalo_minimo_segundos = 1.0

    try:
        while True:
            try:
                dados_brutos = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except (TypeError, ValueError):
                await websocket.send_json({"erro": "Mensagem GPS inválida"})
                continue

            agora_monotonico = time.monotonic()
            if agora_monotonico - ultimo_envio < intervalo_minimo_segundos:
                await websocket.send_json({"erro": "Envio muito frequente, aguarde"})
                continue
            ultimo_envio = agora_monotonico
            try:
                posicao = PosicaoGPSInput(**dados_brutos)
            except Exception:
                await websocket.send_json({"erro": "Payload GPS inválido"})
                continue

            if not esta_na_area_piloto(posicao.latitude, posicao.longitude):
                await websocket.send_json({"erro": "Posição fora da área de cobertura do piloto"})
                continue

            if posicao.pedido_id:
                async with AsyncSessionLocal() as db_check:
                    resultado_pedido = await db_check.execute(
                        select(Pedido).where(Pedido.id == posicao.pedido_id)
                    )
                    pedido_verificado = resultado_pedido.scalar_one_or_none()
                    if pedido_verificado is None or pedido_verificado.motoboy_id != motoboy_id:
                        await websocket.send_json({"erro": "pedido_id não pertence a este motoboy"})
                        continue

            agora = datetime.utcnow()

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

            await gerenciador.broadcast_posicao(
                motoboy_id=motoboy_id,
                latitude=posicao.latitude,
                longitude=posicao.longitude,
                velocidade=posicao.velocidade,
                pedido_id=posicao.pedido_id,
            )

            await websocket.send_json({"status": "ok", "recebido_em": agora.isoformat()})

    except WebSocketDisconnect:
        logger.info(f"Motoboy {motoboy_id} desconectou")
    finally:
        era_sessao_atual = gerenciador.desconectar_motoboy(motoboy_id, websocket)
        if era_sessao_atual:
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
    payload = await _autenticar_websocket(token)
    if payload is None or payload.get("tipo") != "admin":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Acesso restrito a administradores")
        return

    await gerenciador.conectar_admin(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Admin desconectou do painel ao vivo")
    finally:
        gerenciador.desconectar_admin(websocket)


@router.websocket("/ws/cliente/{pedido_id}")
async def websocket_cliente(websocket: WebSocket, pedido_id: str, token: str = Query(...)):
    payload = await _autenticar_websocket(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
        return

    usuario_do_token = payload.get("sub")
    tipo_do_token = payload.get("tipo")

    async with AsyncSessionLocal() as db:
        resultado_pedido = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
        pedido = resultado_pedido.scalar_one_or_none()
        if pedido is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Pedido não encontrado")
            return

        if tipo_do_token != "admin":
            resultado_cliente = await db.execute(
                select(Cliente).where(Cliente.usuario_id == usuario_do_token)
            )
            cliente = resultado_cliente.scalar_one_or_none()
            if cliente is None or pedido.cliente_id != cliente.id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Este pedido não pertence a você")
                return

    await gerenciador.conectar_cliente(pedido_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Cliente desconectou do acompanhamento do pedido {pedido_id}")
    finally:
        gerenciador.desconectar_cliente(pedido_id, websocket)
