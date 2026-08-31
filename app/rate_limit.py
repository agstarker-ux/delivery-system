import time
from collections import defaultdict, deque

from fastapi import Request, HTTPException, status

# Guarda timestamps das últimas tentativas por (rota + IP).
# Em memória: funciona bem pra uma única instância (caso do Render free tier).
_registros: dict[str, deque[float]] = defaultdict(deque)


def limitar_por_ip(max_tentativas: int, janela_segundos: int):
    async def verificador(request: Request) -> None:
        agora = time.monotonic()
        ip = request.client.host if request.client else "desconhecido"
        chave = f"{request.url.path}:{ip}"
        fila = _registros[chave]

        while fila and agora - fila[0] > janela_segundos:
            fila.popleft()

        if len(fila) >= max_tentativas:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde um pouco antes de tentar novamente.",
            )

        fila.append(agora)

    return verificador
