import asyncio
import unittest

from app.websocket_manager import GerenciadorConexoes


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def close(self, code=None, reason=None):
        self.closed = True


class WebSocketManagerTests(unittest.TestCase):
    def test_sessao_antiga_nao_remove_sessao_nova(self):
        async def scenario():
            manager = GerenciadorConexoes()
            antiga = FakeWebSocket()
            nova = FakeWebSocket()

            await manager.conectar_motoboy("motoboy-1", antiga)
            await manager.conectar_motoboy("motoboy-1", nova)

            self.assertTrue(antiga.closed)
            self.assertIs(manager.motoboys_conectados["motoboy-1"], nova)
            self.assertFalse(manager.desconectar_motoboy("motoboy-1", antiga))
            self.assertIs(manager.motoboys_conectados["motoboy-1"], nova)
            self.assertTrue(manager.desconectar_motoboy("motoboy-1", nova))

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
