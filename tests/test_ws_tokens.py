import time
import unittest
from unittest.mock import patch

from app.ws_tokens import gerar_token_ws, validar_token_ws


class WsTokenTests(unittest.TestCase):
    def test_token_e_de_uso_unico(self):
        token = gerar_token_ws("usuario-1")
        self.assertEqual(validar_token_ws(token), "usuario-1")
        self.assertIsNone(validar_token_ws(token))

    def test_token_expira(self):
        with patch("app.ws_tokens.time.time", return_value=100.0):
            token = gerar_token_ws("usuario-2")
        with patch("app.ws_tokens.time.time", return_value=121.0):
            self.assertIsNone(validar_token_ws(token))


if __name__ == "__main__":
    unittest.main()
