"""
Schemas Pydantic — validam dados de entrada e formatam dados de saída da API.
Nunca expomos os modelos ORM diretamente: sempre passam por aqui.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models import StatusPedido, StatusMotoboy


# ---------------------------------------------------------------------------
# AUTENTICAÇÃO
# ---------------------------------------------------------------------------

class RegistroUsuario(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    telefone: str = Field(min_length=10, max_length=20)
    senha: str = Field(min_length=6, max_length=100)
    tipo: str = Field(pattern="^(cliente|motoboy|admin)$")


class LoginRequest(BaseModel):
    telefone: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario_id: str
    tipo: str
    nome: str


# ---------------------------------------------------------------------------
# ENDEREÇO
# ---------------------------------------------------------------------------

class EnderecoCreate(BaseModel):
    apelido: str = "Casa"
    logradouro: str
    numero: str
    bairro: str
    complemento: str | None = None
    referencia: str | None = None
    cidade: str = "Manacapuru"
    estado: str = "AM"
    latitude: float
    longitude: float


class EnderecoResponse(EnderecoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str


# ---------------------------------------------------------------------------
# MOTOBOY
# ---------------------------------------------------------------------------

class MotoboyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: StatusMotoboy
    latitude_atual: float | None
    longitude_atual: float | None
    atualizado_em: datetime | None


class AtualizacaoStatusMotoboy(BaseModel):
    status: StatusMotoboy


# ---------------------------------------------------------------------------
# GPS (WebSocket)
# ---------------------------------------------------------------------------

class PosicaoGPSInput(BaseModel):
    """Payload enviado pelo motoboy via WebSocket a cada atualização de posição."""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    velocidade: float | None = None
    precisao: float | None = None
    pedido_id: str | None = None


class PosicaoGPSBroadcast(BaseModel):
    """Payload que o servidor envia ao admin/cliente conectados via WebSocket."""
    motoboy_id: str
    latitude: float
    longitude: float
    velocidade: float | None = None
    pedido_id: str | None = None
    timestamp: str


# ---------------------------------------------------------------------------
# PEDIDO
# ---------------------------------------------------------------------------

class PedidoCreate(BaseModel):
    endereco_id: str
    origem_nome: str
    origem_latitude: float
    origem_longitude: float
    itens_descricao: str
    valor_total: float = Field(gt=0)
    taxa_entrega: float = Field(ge=0, default=0.0)
    observacoes: str | None = None


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


class PedidoStatusUpdate(BaseModel):
    status: StatusPedido
