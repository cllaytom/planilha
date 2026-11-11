from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

StatusAssinatura = Literal["ATIVO", "INATIVO", "SUSPENSO", "CANCELADO", "TESTE"]
TipoLancamento = Literal["renovacao", "pagamento", "despesa", "estorno"]

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    total: int
    itens: list[T]


# ---------------------------------------------------------------- credenciais
class CredencialIn(BaseModel):
    ordem: int = 1
    usuario: str | None = None
    senha: str | None = None
    servidor: str | None = None
    sistema: str | None = None
    produto: str | None = None
    url: str | None = None
    mac: str | None = None
    device_key: str | None = None
    ativacao_app: date | None = None
    vencimento_app: date | None = None
    aplicativo: str | None = None


class CredencialOut(CredencialIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ------------------------------------------------------------------- produtos
class ProdutoBase(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    duracao_fixa: bool = False
    dias: int = Field(default=30, ge=1, le=3650)
    ativo: bool = True
    observacao: str | None = None


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=60)
    duracao_fixa: bool | None = None
    dias: int | None = Field(default=None, ge=1, le=3650)
    ativo: bool | None = None
    observacao: str | None = None


class ProdutoOut(ProdutoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    criado_em: datetime


# -------------------------------------------------------------------- planos
class PlanoBase(BaseModel):
    nome: str
    produto: str | None = None
    valor: float = 0.0
    dias: int = 30
    conexoes: int = 1
    valor_custo: float = 0.0
    servidor: str | None = None
    dns: str | None = None
    sistema: str | None = None
    ativo: bool = True


class PlanoCreate(PlanoBase):
    pass


class PlanoUpdate(BaseModel):
    nome: str | None = None
    produto: str | None = None
    valor: float | None = None
    dias: int | None = None
    conexoes: int | None = None
    valor_custo: float | None = None
    servidor: str | None = None
    dns: str | None = None
    sistema: str | None = None
    ativo: bool | None = None


class PlanoOut(PlanoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    criado_em: datetime


# ---------------------------------------------------------------- assinaturas
class AssinaturaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    usuario: str | None = None
    contato: str | None = None
    data_cadastro: date | None = None
    status: StatusAssinatura = "ATIVO"

    produto: str | None = None
    plano_nome: str | None = None
    plano_id: int | None = None

    valor: float | None = None
    conexoes: int = 1
    desconto: float = 0.0
    valor_final: float | None = None
    custo: float = 0.0

    forma_pagamento: str | None = None
    vencimento: date | None = None
    dia_cobranca: int | None = Field(default=None, ge=1, le=31)

    observacao: str | None = None
    indicado_por: str | None = None
    codigo_legado: str | None = None
    dados_extras: dict = Field(default_factory=dict)


class AssinaturaCreate(AssinaturaBase):
    credenciais: list[CredencialIn] = Field(default_factory=list)


class AssinaturaUpdate(BaseModel):
    nome: str | None = None
    usuario: str | None = None
    contato: str | None = None
    data_cadastro: date | None = None
    status: StatusAssinatura | None = None
    produto: str | None = None
    plano_nome: str | None = None
    plano_id: int | None = None
    valor: float | None = None
    conexoes: int | None = None
    desconto: float | None = None
    valor_final: float | None = None
    custo: float | None = None
    forma_pagamento: str | None = None
    vencimento: date | None = None
    dia_cobranca: int | None = Field(default=None, ge=1, le=31)
    observacao: str | None = None
    indicado_por: str | None = None
    dados_extras: dict | None = None
    credenciais: list[CredencialIn] | None = None


class AssinaturaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_legado: str | None = None
    nome: str
    usuario: str | None = None
    contato: str | None = None
    status: str
    produto: str | None = None
    plano_nome: str | None = None
    valor_final: float
    vencimento: date | None = None
    situacao: str
    dias_atraso: int | None = None


class AssinaturaOut(AssinaturaResumo):
    data_cadastro: date | None = None
    valor: float
    conexoes: int
    desconto: float
    custo: float
    lucro: float
    forma_pagamento: str | None = None
    dia_cobranca: int | None = None
    observacao: str | None = None
    indicado_por: str | None = None
    plano_id: int | None = None
    dados_extras: dict = Field(default_factory=dict)
    credenciais: list[CredencialOut] = Field(default_factory=list)
    criado_em: datetime
    atualizado_em: datetime


class RenovacaoIn(BaseModel):
    dias: int | None = Field(default=None, gt=0, le=3650)
    valor: float | None = Field(default=None, ge=0)
    forma_pagamento: str | None = None
    plano_nome: str | None = None
    observacao: str | None = None


class MudancaStatusIn(BaseModel):
    motivo: str | None = None


class LancamentoCreate(BaseModel):
    assinatura_id: int | None = None
    tipo: TipoLancamento
    data: date | None = None
    valor: float = Field(ge=0)
    forma_pagamento: str | None = None
    plano_nome: str | None = None
    descricao: str | None = None


class PagamentoIn(BaseModel):
    valor: float = Field(ge=0)
    data: date | None = None
    forma_pagamento: str | None = None
    descricao: str | None = None


class LancamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    assinatura_id: int | None = None
    tipo: str
    data: date
    valor: float
    forma_pagamento: str | None = None
    plano_nome: str | None = None
    descricao: str | None = None


class Dashboard(BaseModel):
    hoje: date
    total: int
    ativas: int
    inativas: int
    suspensas: int
    canceladas: int
    vencidas: int
    vencidas_por_data: int
    vencendo_7_dias: int
    mrr: float
    valor_carteira: float
    recebido_mes: float
    despesas_mes: float
    lucro_mes: float
    por_produto: dict[str, int]
    por_plano: dict[str, int]


class ImportacaoResultado(BaseModel):
    linhas_lidas: int
    criados: int
    atualizados: int
    ignorados: int
    planos_criados: int
    erros: list[str] = Field(default_factory=list)


class PagamentoOut(BaseModel):
    assinatura_id: int
    vencimento_anterior: date | None
    vencimento_novo: date
    valor: float
    lancamento_id: int
