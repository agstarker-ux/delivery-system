"""
Ponto de entrada da aplicação.
Rodar com: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import auth_routes, pedidos, motoboys, websocket_gps, enderecos

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cria as tabelas se não existirem (dev). Em produção use Alembic.
    await init_db()
    logging.info("Banco de dados inicializado.")
    yield
    logging.info("Encerrando aplicação.")


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas HTTP
app.include_router(auth_routes.router)
app.include_router(pedidos.router)
app.include_router(motoboys.router)
app.include_router(enderecos.router)

# Rotas WebSocket (GPS em tempo real)
app.include_router(websocket_gps.router)

# Painel Admin (frontend estático com mapa Leaflet)
app.mount("/admin", StaticFiles(directory="app/static/admin", html=True), name="admin")


@app.get("/", tags=["Status"])
async def raiz():
    return {"status": "online", "servico": settings.APP_NAME}


@app.get("/health", tags=["Status"])
async def health_check():
    return {"status": "ok"}
