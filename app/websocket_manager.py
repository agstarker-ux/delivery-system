"""
Gerenciador central de conexões WebSocket.

Três tipos de cliente WebSocket se conectam aqui:
  - motoboy: ENVIA sua posição GPS periodicamente
  - admin: RECEBE a posição de todos os motoboys (painel ao vivo)
  - cliente: RECEBE a posição do motoboy vinculado ao seu pedido em andamento

Arquitetura: um único "hub" em memória. Para múltiplos servidores/workers
no futuro, isso precisaria migrar para Redis Pub/Sub — mas para começar
(inclusive na Oracle Free, 1 instância), isso resolve bem.
"""
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")


class GerenciadorConexoes:
    def __init__(self) -> None:
        # Conexão ativa de cada motoboy (1 por motoboy)
        self.motoboys_conectados: dict[str, WebSocket] = {}

        # Conexões de admins que querem ver TODOS os motoboys ao vivo
        self.admins_conectados: set[WebSocket] = set()

        # Conexões de clientes esperando o GPS de um pedido específico
        # { pedido_id: {WebSocket, WebSocket, ...} }
        self.clientes_por_pedido: dict[str, set[WebSocket]] = {}

        # Mapeia pedido_id -> motoboy_id, para saber a quem repassar a posição
        self.pedido_para_motoboy: dict[str, str] = {}

    # -- MOTOBOY -----------------------------------------------------------

    async def conectar_motoboy(self, motoboy_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.motoboys_conectados[motoboy_id] = websocket
        logger.info(f"Motoboy {motoboy_id} conectado ao WebSocket de GPS")

    def desconectar_motoboy(self, motoboy_id: str) -> None:
        self.motoboys_conectados.pop(motoboy_id, None)
        logger.info(f"Motoboy {motoboy_id} desconectado")

    def vincular_pedido_a_motoboy(self, pedido_id: str, motoboy_id: str) -> None:
        """Chamado quando um motoboy aceita um pedido — habilita o roteamento do GPS."""
        self.pedido_para_motoboy[pedido_id] = motoboy_id

    def desvincular_pedido(self, pedido_id: str) -> None:
        self.pedido_para_motoboy.pop(pedido_id, None)
        self.clientes_por_pedido.pop(pedido_id, None)

    # -- ADMIN ---------------------------------------------------------------

    async def conectar_admin(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.admins_conectados.add(websocket)
        logger.info("Admin conectado ao painel ao vivo")

    def desconectar_admin(self, websocket: WebSocket) -> None:
        self.admins_conectados.discard(websocket)

    # -- CLIENTE --------------------------------------------------------------

    async def conectar_cliente(self, pedido_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clientes_por_pedido.setdefault(pedido_id, set()).add(websocket)
        logger.info(f"Cliente conectado acompanhando pedido {pedido_id}")

    def desconectar_cliente(self, pedido_id: str, websocket: WebSocket) -> None:
        if pedido_id in self.clientes_por_pedido:
            self.clientes_por_pedido[pedido_id].discard(websocket)
            if not self.clientes_por_pedido[pedido_id]:
                del self.clientes_por_pedido[pedido_id]

    # -- BROADCAST DE POSIÇÃO --------------------------------------------------

    async def broadcast_posicao(
        self,
        motoboy_id: str,
        latitude: float,
        longitude: float,
        velocidade: float | None = None,
        pedido_id: str | None = None,
    ) -> None:
        """
        Recebe a posição de um motoboy e repassa:
          1. Para TODOS os admins conectados (painel ao vivo geral)
          2. Para os clientes acompanhando o pedido específico, se houver
        """
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

        # 1. Envia para todos os admins — remove conexões mortas encontradas
        admins_mortos = set()
        for admin_ws in self.admins_conectados:
            try:
                await admin_ws.send_text(payload)
            except Exception:
                admins_mortos.add(admin_ws)
        self.admins_conectados -= admins_mortos

        # 2. Envia para clientes do pedido em questão
        if pedido_id and pedido_id in self.clientes_por_pedido:
            clientes_mortos = set()
            for cliente_ws in self.clientes_por_pedido[pedido_id]:
                try:
                    await cliente_ws.send_text(payload)
                except Exception:
                    clientes_mortos.add(cliente_ws)
            self.clientes_por_pedido[pedido_id] -= clientes_mortos

    async def notificar_admins(self, tipo_evento: str, dados: dict) -> None:
        """
        Uso genérico: notifica admins sobre eventos que não são GPS puro
        (ex: novo pedido criado, pedido cancelado, motoboy ficou offline).
        """
        mensagem = {"tipo": tipo_evento, **dados, "timestamp": datetime.now(timezone.utc).isoformat()}
        payload = json.dumps(mensagem)
        admins_mortos = set()
        for admin_ws in self.admins_conectados:
            try:
                await admin_ws.send_text(payload)
            except Exception:
                admins_mortos.add(admin_ws)
        self.admins_conectados -= admins_mortos


# Instância única compartilhada por toda a aplicação
gerenciador = GerenciadorConexoes()
