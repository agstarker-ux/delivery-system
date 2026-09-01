import unittest

from pydantic import ValidationError

from app.models import StatusPedido, transicao_e_valida
from app.schemas import EnderecoCreate, PedidoCreate, PosicaoGPSInput, RegistroUsuario


class ContractTests(unittest.TestCase):
    def test_registro_publico_so_aceita_cliente(self):
        usuario = RegistroUsuario(
            nome="Cliente Teste",
            telefone="92999999999",
            senha="senha-segura",
        )
        self.assertEqual(usuario.tipo, "cliente")
        with self.assertRaises(ValidationError):
            RegistroUsuario(
                nome="Motoboy Teste",
                telefone="92999999998",
                senha="senha-segura",
                tipo="motoboy",
            )

    def test_gps_rejeita_valores_impossiveis(self):
        PosicaoGPSInput(latitude=-3.1, longitude=-58.4, velocidade=40)
        with self.assertRaises(ValidationError):
            PosicaoGPSInput(latitude=-3.1, longitude=-58.4, velocidade=-1)
        with self.assertRaises(ValidationError):
            PosicaoGPSInput(latitude=-3.1, longitude=-58.4, latitude_extra=1)

    def test_textos_e_valores_tem_limites(self):
        with self.assertRaises(ValidationError):
            EnderecoCreate(
                logradouro="Rua",
                numero="1",
                bairro="Bairro",
                latitude=-3.1,
                longitude=-58.4,
                estado="Amazonas",
            )
        with self.assertRaises(ValidationError):
            PedidoCreate(
                endereco_id="endereco",
                origem_nome="Loja",
                origem_latitude=-3.1,
                origem_longitude=-58.4,
                itens_descricao="Produto",
                valor_total=100001,
            )

    def test_transicoes_de_pedido(self):
        self.assertTrue(transicao_e_valida(StatusPedido.ACEITO, StatusPedido.A_CAMINHO_COLETA))
        self.assertFalse(transicao_e_valida(StatusPedido.ENTREGUE, StatusPedido.ACEITO))


if __name__ == "__main__":
    unittest.main()
