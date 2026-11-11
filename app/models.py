from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .utils import situacao as calcular_situacao


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Produto(Base):
    """Catalogo de produtos vendidos (ex.: IPTV, Internet)."""

    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    # duracao_fixa = sempre o mesmo numero de dias (ex.: IPTV, 30 dias);
    # duracao_fixa = False permite mudar os dias (ex.: Internet).
    duracao_fixa: Mapped[bool] = mapped_column(Boolean, default=False)
    dias: Mapped[int] = mapped_column(Integer, default=30)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Plano(Base):
    __tablename__ = "planos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    produto: Mapped[str | None] = mapped_column(String(60), nullable=True)
    valor: Mapped[float] = mapped_column(Float, default=0.0)
    dias: Mapped[int] = mapped_column(Integer, default=30)
    conexoes: Mapped[int] = mapped_column(Integer, default=1)
    valor_custo: Mapped[float] = mapped_column(Float, default=0.0)
    servidor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dns: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sistema: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Assinatura(Base):
    __tablename__ = "assinaturas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_legado: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(160), index=True)
    usuario: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    contato: Mapped[str | None] = mapped_column(String(80), nullable=True)
    data_cadastro: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ATIVO", index=True)

    produto: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    plano_nome: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    plano_id: Mapped[int | None] = mapped_column(ForeignKey("planos.id", ondelete="SET NULL"), nullable=True)

    valor: Mapped[float] = mapped_column(Float, default=0.0)
    conexoes: Mapped[int] = mapped_column(Integer, default=1)
    desconto: Mapped[float] = mapped_column(Float, default=0.0)
    valor_final: Mapped[float] = mapped_column(Float, default=0.0)
    custo: Mapped[float] = mapped_column(Float, default=0.0)
    lucro: Mapped[float] = mapped_column(Float, default=0.0)

    forma_pagamento: Mapped[str | None] = mapped_column(String(40), nullable=True)
    vencimento: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    dia_cobranca: Mapped[int | None] = mapped_column(Integer, nullable=True)

    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    indicado_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dados_extras: Mapped[dict] = mapped_column(JSON, default=dict)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora, onupdate=agora
    )

    plano: Mapped[Plano | None] = relationship(lazy="joined")
    credenciais: Mapped[list[Credencial]] = relationship(
        back_populates="assinatura",
        cascade="all, delete-orphan",
        order_by="Credencial.ordem",
    )
    lancamentos: Mapped[list[Lancamento]] = relationship(
        back_populates="assinatura", cascade="all, delete-orphan"
    )

    @property
    def situacao(self) -> str:
        return calcular_situacao(self.vencimento, self.status)[0]

    @property
    def dias_atraso(self) -> int | None:
        return calcular_situacao(self.vencimento, self.status)[1]


class Credencial(Base):
    """Cada assinatura pode ter de 1 a 5 acessos (usuario/senha por sistema)."""

    __tablename__ = "credenciais"

    id: Mapped[int] = mapped_column(primary_key=True)
    assinatura_id: Mapped[int] = mapped_column(
        ForeignKey("assinaturas.id", ondelete="CASCADE"), index=True
    )
    ordem: Mapped[int] = mapped_column(Integer, default=1)
    usuario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    senha: Mapped[str | None] = mapped_column(String(120), nullable=True)
    servidor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sistema: Mapped[str | None] = mapped_column(String(80), nullable=True)
    produto: Mapped[str | None] = mapped_column(String(60), nullable=True)
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mac: Mapped[str | None] = mapped_column(String(60), nullable=True)
    device_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ativacao_app: Mapped[date | None] = mapped_column(Date, nullable=True)
    vencimento_app: Mapped[date | None] = mapped_column(Date, nullable=True)
    aplicativo: Mapped[str | None] = mapped_column(String(80), nullable=True)

    assinatura: Mapped[Assinatura] = relationship(back_populates="credenciais")


class Lancamento(Base):
    """Financeiro: renovacoes, pagamentos avulsos, despesas e estornos."""

    __tablename__ = "lancamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    assinatura_id: Mapped[int | None] = mapped_column(
        ForeignKey("assinaturas.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tipo: Mapped[str] = mapped_column(String(20), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    valor: Mapped[float] = mapped_column(Float, default=0.0)
    forma_pagamento: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plano_nome: Mapped[str | None] = mapped_column(String(80), nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    assinatura: Mapped[Assinatura | None] = relationship(back_populates="lancamentos")


class Evento(Base):
    """Auditoria de tudo que a API (ou o agente) alterou."""

    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    entidade: Mapped[str] = mapped_column(String(40), index=True)
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String(40))
    antes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    depois: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    origem: Mapped[str] = mapped_column(String(40), default="api")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
