import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")


class GerenciadorConexoes:
    def __init__(self) -> None:
        self.motoboys_conectados: dict[str, WebSocket] = {}
        self.admins_conectados: set[WebSocket] = set()
        self.clientes_por_pedido: dict[str, set[WebSocket]] = {}
        self.pedido_para_motoboy: dict[str, str] = {}

    async def conectar_motoboy(self, motoboy_id: str, websocket: WebSocket) -> None:
        antiga = self.motoboys_conectados.get(motoboy_id)
        if antiga is not None and antiga is not websocket:
            try:
                await antiga.close(code=1000, reason="Nova sessão iniciada")
            except Exception:
                logger.debug("Não foi possível fechar a sessão anterior do motoboy %s", motoboy_id)
        await websocket.accept()
        self.motoboys_conectados[motoboy_id] = websocket
        logger.info("Motoboy %s conectado ao WebSocket de GPS", motoboy_id)

    def desconectar_motoboy(self, motoboy_id: str, websocket: WebSocket | None = None) -> bool:
        atual = self.motoboys_conectados.get(motoboy_id)
        if atual is None or (websocket is not None and atual is not websocket):
            return False
        self.motoboys_conectados.pop(motoboy_id, None)
        logger.info("Motoboy %s desconectado", motoboy_id)
        return True

    def vincular_pedido_a_motoboy(self, pedido_id: str, motoboy_id: str) -> None:
        self.pedido_para_motoboy[pedido_id] = motoboy_id

    def desvincular_pedido(self, pedido_id: str) -> None:
        self.pedido_para_motoboy.pop(pedido_id, None)
        self.clientes_por_pedido.pop(pedido_id, None)

    async def conectar_admin(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.admins_conectados.add(websocket)
        logger.info("Admin conectado ao painel ao vivo")

    def desconectar_admin(self, websocket: WebSocket) -> None:
        self.admins_conectados.discard(websocket)

    async def conectar_cliente(self, pedido_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clientes_por_pedido.setdefault(pedido_id, set()).add(websocket)
        logger.info("Cliente conectado acompanhando pedido %s", pedido_id)

    def desconectar_cliente(self, pedido_id: str, websocket: WebSocket) -> None:
        if pedido_id in self.clientes_por_pedido:
            self.clientes_por_pedido[pedido_id].discard(websocket)
            if not self.clientes_por_pedido[pedido_id]:
                del self.clientes_por_pedido[pedido_id]

    async def broadcast_posicao(
        self,
        motoboy_id: str,
        latitude: float,
        longitude: float,
        velocidade: float | None = None,
        pedido_id: str | None = None,
    ) -> None:
        mensagem = {
            "tipo": "posicao_gps",
            "motoboy_id": motoboy_id,
            "latitude": latitude,
            "longitude": longitude,
            "velocidade": velocidade,
            "pedido_id": pedido_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(mensagem)
        admins_mortos = set()
        for admin_ws in self.admins_conectados:
            try:
                await admin_ws.send_text(payload)
            except Exception:
                admins_mortos.add(admin_ws)
        self.admins_conectados -= admins_mortos

        if pedido_id and pedido_id in self.clientes_por_pedido:
            clientes_mortos = set()
            for cliente_ws in self.clientes_por_pedido[pedido_id]:
                try:
                    await cliente_ws.send_text(payload)
                except Exception:
                    clientes_mortos.add(cliente_ws)
            self.clientes_por_pedido[pedido_id] -= clientes_mortos

    async def notificar_admins(self, tipo_evento: str, dados: dict) -> None:
        mensagem = {
            "tipo": tipo_evento,
            **dados,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(mensagem)
        admins_mortos = set()
        for admin_ws in self.admins_conectados:
            try:
                await admin_ws.send_text(payload)
            except Exception:
                admins_mortos.add(admin_ws)
        self.admins_conectados -= admins_mortos


gerenciador = GerenciadorConexoes()
