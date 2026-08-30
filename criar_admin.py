import asyncio
import sys

from app.database import AsyncSessionLocal
from app.auth import hash_senha
from app.models import Usuario


async def criar_admin(nome: str, telefone: str, senha: str) -> None:
    async with AsyncSessionLocal() as db:
        usuario = Usuario(
            nome=nome,
            telefone=telefone,
            senha_hash=hash_senha(senha),
            tipo="admin",
        )
        db.add(usuario)
        await db.commit()
        print(f"Admin criado: {usuario.id} ({usuario.telefone})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python3 criar_admin.py <nome> <telefone> <senha>")
        sys.exit(1)

    asyncio.run(criar_admin(sys.argv[1], sys.argv[2], sys.argv[3]))
