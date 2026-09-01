"""
Simulador de GPS — conecta como um motoboy via WebSocket e manda
posições falsas em loop, pra testar o painel admin sem precisar
de um celular de verdade em campo.
"""
import asyncio
import json
import math
import random

import websockets

# --- Configuração ---------------------------------------------------------
import os

MOTOBOY_ID = os.environ["SIMULADOR_MOTOBOY_ID"]
TOKEN = os.environ["SIMULADOR_MOTOBOY_TOKEN"]
PEDIDO_ID = os.getenv("SIMULADOR_PEDIDO_ID") or None

URL = f"ws://localhost:8000/ws/motoboy/{MOTOBOY_ID}?token={TOKEN}"

# Centro do Poranga (mesma coordenada estimada do config.py)
CENTRO_LAT = -3.115
CENTRO_LON = -58.435
RAIO_MOVIMENTO = 0.006  # graus (~1.1km) — o quanto o motoboy "anda" ao redor do centro


async def simular():
    print(f"Conectando como motoboy {MOTOBOY_ID}...")
    async with websockets.connect(URL) as ws:
        print("Conectado! Enviando GPS a cada 3 segundos (Ctrl+C pra parar)")

        angulo = 0.0
        while True:
            # Movimento circular simples ao redor do centro do Poranga
            angulo += 0.05
            lat = CENTRO_LAT + RAIO_MOVIMENTO * math.sin(angulo)
            lon = CENTRO_LON + RAIO_MOVIMENTO * math.cos(angulo)
            velocidade = round(random.uniform(15, 40), 1)

            payload = {
                "latitude": lat,
                "longitude": lon,
                "velocidade": velocidade,
                "pedido_id": PEDIDO_ID,
            }

            await ws.send(json.dumps(payload))
            resposta = await ws.recv()
            print(f"Enviado: lat={lat:.6f} lon={lon:.6f} vel={velocidade}km/h | Servidor: {resposta}")

            await asyncio.sleep(1.5)


if __name__ == "__main__":
    try:
        asyncio.run(simular())
    except KeyboardInterrupt:
        print("\nSimulação encerrada.")
