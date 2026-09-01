import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db
from app.routers import auth_routes, pedidos, motoboys, websocket_gps, enderecos

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logging.info("Banco de dados inicializado.")
    yield
    logging.info("Encerrando aplicação.")


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(auth_routes.router)
app.include_router(pedidos.router)
app.include_router(motoboys.router)
app.include_router(enderecos.router)
app.include_router(websocket_gps.router)


@app.get("/status", tags=["Status"])
async def status_servico():
    return {"status": "online", "servico": settings.APP_NAME}


@app.get("/health", tags=["Status"])
async def health_check():
    return {"status": "ok"}


app.mount("/admin", StaticFiles(directory="app/static/admin", html=True), name="admin")
app.mount("/cliente", StaticFiles(directory="app/static/cliente", html=True), name="cliente")
app.mount("/motoboy", StaticFiles(directory="app/static/motoboy", html=True), name="motoboy")
app.mount("/", StaticFiles(directory="app/static/inicio", html=True), name="inicio")
