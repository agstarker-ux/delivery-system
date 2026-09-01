from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import StatusMotoboy, StatusPedido


class BaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegistroUsuario(BaseInput):
    nome: str = Field(min_length=2, max_length=120)
    telefone: str = Field(min_length=10, max_length=20, pattern=r"^[0-9+()\-\s]+$")
    senha: str = Field(min_length=6, max_length=72)
    # A criação pública fica limitada a clientes; motoboys são criados pelo administrador.
    tipo: Literal["cliente"] = "cliente"


class LoginRequest(BaseInput):
    telefone: str = Field(min_length=1, max_length=20)
    senha: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario_id: str
    tipo: str
    nome: str


class EnderecoCreate(BaseInput):
    apelido: str = Field(default="Casa", min_length=1, max_length=50)
    logradouro: str = Field(min_length=1, max_length=200)
    numero: str = Field(min_length=1, max_length=20)
    bairro: str = Field(min_length=1, max_length=100)
    complemento: str | None = Field(default=None, max_length=200)
    referencia: str | None = Field(default=None, max_length=200)
    cidade: str = Field(default="Itacoatiara", min_length=1, max_length=100)
    estado: str = Field(default="AM", min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class EnderecoResponse(EnderecoCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: str


class MotoboyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: StatusMotoboy
    latitude_atual: float | None
    longitude_atual: float | None
    atualizado_em: datetime | None


class AtualizacaoStatusMotoboy(BaseInput):
    status: StatusMotoboy


class PosicaoGPSInput(BaseInput):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    velocidade: float | None = Field(default=None, ge=0, le=250, allow_inf_nan=False)
    precisao: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    pedido_id: str | None = Field(default=None, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")


class PosicaoGPSBroadcast(BaseModel):
    motoboy_id: str
    latitude: float
    longitude: float
    velocidade: float | None = None
    pedido_id: str | None = None
    timestamp: str


class PedidoCreate(BaseInput):
    endereco_id: str = Field(min_length=1, max_length=36)
    origem_nome: str = Field(min_length=1, max_length=150)
    origem_latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    origem_longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    itens_descricao: str = Field(min_length=1, max_length=2000)
    valor_total: float = Field(gt=0, le=100000, allow_inf_nan=False)
    taxa_entrega: float = Field(ge=0, le=100000, default=0.0, allow_inf_nan=False)
    observacoes: str | None = Field(default=None, max_length=1000)


class PedidoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    cliente_id: str
    motoboy_id: str | None
    endereco_id: str
    status: StatusPedido
    origem_nome: str
    origem_latitude: float
    origem_longitude: float
    itens_descricao: str
    valor_total: float
    taxa_entrega: float
    observacoes: str | None
    criado_em: datetime
    aceito_em: datetime | None
    entregue_em: datetime | None


class PedidoStatusUpdate(BaseInput):
    status: StatusPedido
