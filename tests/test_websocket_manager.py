import asyncio
import unittest

from app.websocket_manager import GerenciadorConexoes


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_text = []

    async def accept(self):
        self.accepted = True

    async def close(self, code=None, reason=None):
        self.closed = True

    async def send_text(self, payload):
        self.sent_text.append(payload)


class WebSocketManagerTests(unittest.TestCase):
    def test_broadcast_de_posicao_gera_json_para_o_admin(self):
        async def scenario():
            manager = GerenciadorConexoes()
            admin = FakeWebSocket()
            await manager.conectar_admin(admin)
            await manager.broadcast_posicao("motoboy-1", -3.11, -58.45, 20.0, None)
            self.assertEqual(len(admin.sent_text), 1)
            self.assertIn('"tipo": "posicao_gps"', admin.sent_text[0])
            self.assertIn('"motoboy_id": "motoboy-1"', admin.sent_text[0])

        asyncio.run(scenario())

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
