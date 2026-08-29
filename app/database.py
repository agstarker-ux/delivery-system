"""
Conexão assíncrona com PostgreSQL usando SQLAlchemy 2.0 + asyncpg.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Engine assíncrona — pool de conexões gerenciado pelo SQLAlchemy
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,       # loga as queries SQL (desligue em produção pesada)
    pool_size=10,               # conexões simultâneas mantidas abertas
    max_overflow=20,            # conexões extras permitidas em pico
    pool_pre_ping=True,         # testa conexão antes de usar (evita erro de conexão caída)
)

# Fábrica de sessões assíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM."""
    pass


async def get_db():
    """
    Dependency do FastAPI: fornece uma sessão de banco por requisição
    e garante que ela seja fechada ao final, mesmo em caso de erro.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Cria todas as tabelas no banco (usado em desenvolvimento).
    Em produção, prefira migrations com Alembic.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
