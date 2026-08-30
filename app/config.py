from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://delivery_user:delivery_pass@localhost:5432/delivery_db"

    JWT_SECRET_KEY: str = "TROQUE_ESSA_CHAVE_EM_PRODUCAO_gere_com_openssl_rand_hex_32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    APP_NAME: str = "Sistema de Delivery"
    DEBUG: bool = True

    CORS_ORIGINS: list[str] = ["*"]

    AREA_PILOTO_ATIVA: bool = True
    AREA_PILOTO_NOME: str = "Bairro Poranga, Itacoatiara/AM"
    AREA_PILOTO_LATITUDE: float = -3.115
    AREA_PILOTO_LONGITUDE: float = -58.435
    AREA_PILOTO_RAIO_KM: float = 3.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
