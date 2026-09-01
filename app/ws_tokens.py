import secrets
import time

_tokens = {}
_TTL_SEGUNDOS = 20

def gerar_token_ws(usuario_id: str) -> str:
    # Limpa tokens expirados antes de adicionar novos para evitar crescimento ilimitado.
    limpar_tokens_expirados()
    token = secrets.token_urlsafe(32)
    _tokens[token] = (usuario_id, time.time() + _TTL_SEGUNDOS)
    return token

def validar_token_ws(token: str) -> str | None:
    dados = _tokens.pop(token, None)
    if dados is None:
        return None
    usuario_id, expira_em = dados
    if time.time() > expira_em:
        return None
    return usuario_id

def limpar_tokens_expirados():
    agora = time.time()
    expirados = [t for t, (_, exp) in _tokens.items() if agora > exp]
    for t in expirados:
        _tokens.pop(t, None)
