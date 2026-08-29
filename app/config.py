"""
Configurações centrais do sistema.
Lê tudo de variáveis de ambiente (.env) — nunca hardcode credenciais aqui.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Banco de dados ---
    # Formato produção (Postgres):
    #   postgresql+asyncpg://usuario:senha@host:5432/nome_do_banco
    DATABASE_URL: str = "postgresql+asyncpg://delivery_user:delivery_pass@localhost:5432/delivery_db"

    # --- JWT / Autenticação ---
    JWT_SECRET_KEY: str = "TROQUE_ESSA_CHAVE_EM_PRODUCAO_gere_com_openssl_rand_hex_32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 horas

    # --- App ---
    APP_NAME: str = "Sistema de Delivery"
    DEBUG: bool = True

    # --- CORS (domínios que podem acessar a API) ---
    # Em produção, restrinja aos domínios reais do app cliente/motoboy/admin
    CORS_ORIGINS: list[str] = ["*"]

    # --- Área piloto: bairro Poranga, Itacoatiara/AM ---
    # Centro aproximado do bairro (CEPs 69100-330 a 69100-627).
    # Ajuste estas coordenadas quando tiver um ponto de referência mais preciso
    # (ex: coordenada real de um estabelecimento do bairro via GPS do celular).
    AREA_PILOTO_ATIVA: bool = True
    AREA_PILOTO_NOME: str = "Bairro Poranga, Itacoatiara/AM"
    AREA_PILOTO_LATITUDE: float = -3.115
    AREA_PILOTO_LONGITUDE: float = -58.435
    AREA_PILOTO_RAIO_KM: float = 3.0  # raio de cobertura a partir do centro

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
