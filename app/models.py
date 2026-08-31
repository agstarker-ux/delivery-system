import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, ForeignKey, Enum, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class StatusPedido(str, enum.Enum):
    PENDENTE = "pendente"
    ACEITO = "aceito"
    A_CAMINHO_COLETA = "a_caminho_coleta"
    COLETADO = "coletado"
    A_CAMINHO_ENTREGA = "a_caminho_entrega"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


# Transições válidas: de onde -> pra onde pode ir.
# ACEITO só é alcançado via /pedidos/{id}/aceitar, nunca por essa rota de status.
TRANSICOES_VALIDAS_PEDIDO: dict["StatusPedido", set["StatusPedido"]] = {
    StatusPedido.PENDENTE: {StatusPedido.CANCELADO},
    StatusPedido.ACEITO: {StatusPedido.A_CAMINHO_COLETA, StatusPedido.CANCELADO},
    StatusPedido.A_CAMINHO_COLETA: {StatusPedido.COLETADO, StatusPedido.CANCELADO},
    StatusPedido.COLETADO: {StatusPedido.A_CAMINHO_ENTREGA, StatusPedido.CANCELADO},
    StatusPedido.A_CAMINHO_ENTREGA: {StatusPedido.ENTREGUE, StatusPedido.CANCELADO},
    StatusPedido.ENTREGUE: set(),
    StatusPedido.CANCELADO: set(),
}


def transicao_e_valida(status_atual: "StatusPedido", novo_status: "StatusPedido") -> bool:
    return novo_status in TRANSICOES_VALIDAS_PEDIDO.get(status_atual, set())


class StatusMotoboy(str, enum.Enum):
    OFFLINE = "offline"
    DISPONIVEL = "disponivel"
    EM_ENTREGA = "em_entrega"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cliente_perfil: Mapped["Cliente"] = relationship(back_populates="usuario", uselist=False, cascade="all, delete-orphan")
    motoboy_perfil: Mapped["Motoboy"] = relationship(back_populates="usuario", uselist=False, cascade="all, delete-orphan")


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="cliente_perfil")
    enderecos: Mapped[list["Endereco"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")
    pedidos: Mapped[list["Pedido"]] = relationship(back_populates="cliente")


class Endereco(Base):
    __tablename__ = "enderecos"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))

    apelido: Mapped[str] = mapped_column(String(50), default="Casa")
    logradouro: Mapped[str] = mapped_column(String(200), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    bairro: Mapped[str] = mapped_column(String(100), nullable=False)
    complemento: Mapped[str] = mapped_column(String(200), nullable=True)
    referencia: Mapped[str] = mapped_column(String(200), nullable=True)
    cidade: Mapped[str] = mapped_column(String(100), default="Itacoatiara")
    estado: Mapped[str] = mapped_column(String(2), default="AM")

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    cliente: Mapped["Cliente"] = relationship(back_populates="enderecos")


class Motoboy(Base):
    __tablename__ = "motoboys"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True)

    placa_veiculo: Mapped[str] = mapped_column(String(10), nullable=True)
    cnh: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[StatusMotoboy] = mapped_column(Enum(StatusMotoboy), default=StatusMotoboy.OFFLINE)

    latitude_atual: Mapped[float] = mapped_column(Float, nullable=True)
    longitude_atual: Mapped[float] = mapped_column(Float, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="motoboy_perfil")
    pedidos: Mapped[list["Pedido"]] = relationship(back_populates="motoboy")
    historico_posicoes: Mapped[list["PosicaoGPS"]] = relationship(back_populates="motoboy", cascade="all, delete-orphan")


class PosicaoGPS(Base):
    __tablename__ = "posicoes_gps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    motoboy_id: Mapped[str] = mapped_column(ForeignKey("motoboys.id", ondelete="CASCADE"), index=True)
    pedido_id: Mapped[str] = mapped_column(ForeignKey("pedidos.id", ondelete="SET NULL"), nullable=True, index=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    velocidade: Mapped[float] = mapped_column(Float, nullable=True)
    precisao: Mapped[float] = mapped_column(Float, nullable=True)
    registrado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    motoboy: Mapped["Motoboy"] = relationship(back_populates="historico_posicoes")


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id", ondelete="RESTRICT"), index=True)
    motoboy_id: Mapped[str] = mapped_column(ForeignKey("motoboys.id", ondelete="SET NULL"), nullable=True, index=True)
    endereco_id: Mapped[str] = mapped_column(ForeignKey("enderecos.id", ondelete="RESTRICT"))

    status: Mapped[StatusPedido] = mapped_column(Enum(StatusPedido), default=StatusPedido.PENDENTE, index=True)

    origem_nome: Mapped[str] = mapped_column(String(150), nullable=False)
    origem_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    origem_longitude: Mapped[float] = mapped_column(Float, nullable=False)

    itens_descricao: Mapped[str] = mapped_column(Text, nullable=False)
    valor_total: Mapped[float] = mapped_column(Float, nullable=False)
    taxa_entrega: Mapped[float] = mapped_column(Float, default=0.0)
    observacoes: Mapped[str] = mapped_column(Text, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    aceito_em: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    entregue_em: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="pedidos")
    motoboy: Mapped["Motoboy"] = relationship(back_populates="pedidos")
    endereco: Mapped["Endereco"] = relationship()
