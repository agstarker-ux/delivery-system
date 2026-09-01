import asyncio
import unittest

import httpx

from app.main import app


async def request(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


class AppSmokeTests(unittest.TestCase):
    def test_health(self):
        response = asyncio.run(request("/health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_paginas_estaticas(self):
        for path in ("/", "/cliente/", "/motoboy/", "/admin/"):
            with self.subTest(path=path):
                response = asyncio.run(request(path))
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_endpoint_de_pedido_ativo_registado(self):
        paths = {path for path in app.openapi().get("paths", {})}
        self.assertIn("/pedidos/me/atual", paths)


if __name__ == "__main__":
    unittest.main()
