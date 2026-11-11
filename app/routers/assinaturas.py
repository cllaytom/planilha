from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auditoria import registrar
from ..database import get_db
from ..models import Assinatura, Credencial, Lancamento, Plano, Produto
from ..schemas import (
    AssinaturaCreate,
    AssinaturaOut,
    AssinaturaResumo,
    AssinaturaUpdate,
    LancamentoOut,
    PagamentoIn,
    PagamentoOut,
    Pagina,
    RenovacaoIn,
)
from ..security import verificar_api_key

router = APIRouter(
    prefix="/assinaturas",
    tags=["assinaturas"],
    dependencies=[Depends(verificar_api_key)],
)

STATUS_VALIDOS = {"ATIVO", "INATIVO", "SUSPENSO", "CANCELADO", "TESTE"}


def _buscar(db: Session, assinatura_id: int) -> Assinatura:
    ass = db.get(Assinatura, assinatura_id)
    if not ass:
        raise HTTPException(status_code=404, detail=f"Assinatura {assinatura_id} nao encontrada.")
    return ass


def _resolver_plano(db: Session, plano_id: int | None, plano_nome: str | None) -> Plano | None:
    if plano_id:
        plano = db.get(Plano, plano_id)
        if not plano:
            raise HTTPException(status_code=422, detail=f"Plano {plano_id} nao encontrado.")
        return plano
    if plano_nome:
        return db.scalar(select(Plano).where(func.upper(Plano.nome) == plano_nome.strip().upper()))
    return None


def _dias_do_produto(db: Session, produto_nome: str | None, dias_pedidos: int | None, dias_plano: int | None) -> int:
    """Produto de duracao fixa (ex.: IPTV) ignora os dias pedidos; flexivel (ex.: Internet) aceita."""
    produto = None
    if produto_nome:
        produto = db.scalar(select(Produto).where(func.upper(Produto.nome) == produto_nome.strip().upper()))
    if produto and produto.duracao_fixa:
        return produto.dias
    return dias_pedidos or dias_plano or (produto.dias if produto else 30)


def _recalcular(ass: Assinatura) -> None:
    ass.valor_final = round((ass.valor or 0.0) - (ass.desconto or 0.0), 2)
    ass.lucro = round((ass.valor_final or 0.0) - (ass.custo or 0.0), 2)


def _aplicar_situacao(stmt, situacao_filtro: str, hoje: date):
    filtro = situacao_filtro.strip().lower()
    em_dia = Assinatura.status.notin_(["CANCELADO", "INATIVO", "SUSPENSO"])
    if filtro in ("vencida", "vencidas"):
        return stmt.where(Assinatura.vencimento < hoje).where(em_dia)
    if filtro in ("vencendo", "vencendo_7"):
        return stmt.where(Assinatura.vencimento.between(hoje, hoje + timedelta(days=7))).where(em_dia)
    if filtro in ("vence_hoje",):
        return stmt.where(Assinatura.vencimento == hoje).where(em_dia)
    if filtro in ("ativa", "ativas"):
        return stmt.where(Assinatura.vencimento > hoje + timedelta(days=7)).where(em_dia)
    if filtro in ("inativa", "inativas"):
        return stmt.where(Assinatura.status == "INATIVO")
    if filtro in ("suspensa", "suspensas"):
        return stmt.where(Assinatura.status == "SUSPENSO")
    if filtro in ("cancelada", "canceladas"):
        return stmt.where(Assinatura.status == "CANCELADO")
    if filtro in ("sem_vencimento",):
        return stmt.where(Assinatura.vencimento.is_(None))
    raise HTTPException(
        status_code=422,
        detail="situacao invalida. Use: ativa, vencendo, vencida, vence_hoje, inativa, "
               "suspensa, cancelada, sem_vencimento.",
    )


@router.get("", response_model=Pagina[AssinaturaResumo], summary="Listar assinaturas")
def listar(
    q: str | None = Query(default=None, description="Busca por nome, usuario, contato ou ID legado"),
    status: str | None = Query(default=None, description="ATIVO, INATIVO, SUSPENSO, CANCELADO, TESTE"),
    produto: str | None = None,
    plano: str | None = None,
    situacao: str | None = Query(default=None, description="Filtro derivado do vencimento"),
    vencendo_em_dias: int | None = Query(default=None, ge=0, le=365),
    atrasadas: bool = Query(default=False, description="Somente vencidas e nao canceladas"),
    ordenar_por: str = Query(default="nome", description="nome | vencimento | valor | id"),
    ordem: str = Query(default="asc", description="asc | desc"),
    limite: int = Query(default=50, ge=1, le=500),
    deslocamento: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    hoje = date.today()
    stmt = select(Assinatura)

    if q:
        termo = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Assinatura.nome.ilike(termo),
                Assinatura.usuario.ilike(termo),
                Assinatura.contato.ilike(termo),
                Assinatura.codigo_legado.ilike(termo),
            )
        )
    if status:
        stmt = stmt.where(Assinatura.status == status.strip().upper())
    if produto:
        stmt = stmt.where(func.upper(Assinatura.produto) == produto.strip().upper())
    if plano:
        stmt = stmt.where(func.upper(Assinatura.plano_nome) == plano.strip().upper())
    if situacao:
        stmt = _aplicar_situacao(stmt, situacao, hoje)
    if vencendo_em_dias is not None:
        stmt = stmt.where(Assinatura.vencimento.between(hoje, hoje + timedelta(days=vencendo_em_dias)))
    if atrasadas:
        stmt = stmt.where(Assinatura.vencimento < hoje).where(
            Assinatura.status.notin_(["CANCELADO", "INATIVO", "SUSPENSO"])
        )

    colunas = {
        "nome": Assinatura.nome,
        "vencimento": Assinatura.vencimento,
        "valor": Assinatura.valor_final,
        "id": Assinatura.id,
    }
    coluna = colunas.get(ordenar_por.lower(), Assinatura.nome)
    stmt = stmt.order_by(coluna.desc() if ordem.lower() == "desc" else coluna.asc())

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    itens = db.scalars(stmt.limit(limite).offset(deslocamento)).all()
    return {"total": total, "itens": itens}


@router.get("/{assinatura_id}", response_model=AssinaturaOut, summary="Detalhar assinatura")
def detalhar(assinatura_id: int, db: Session = Depends(get_db)):
    return _buscar(db, assinatura_id)


@router.post("", response_model=AssinaturaOut, status_code=201, summary="Criar assinatura")
def criar(payload: AssinaturaCreate, db: Session = Depends(get_db)):
    dados = payload.model_dump(exclude={"credenciais"})
    plano = _resolver_plano(db, dados.get("plano_id"), dados.get("plano_nome"))

    if dados.get("data_cadastro") is None:
        dados["data_cadastro"] = date.today()
    if dados.get("valor") is None:
        dados["valor"] = plano.valor if plano else 0.0
    if dados.get("valor_final") is None:
        dados["valor_final"] = round(dados["valor"] - (dados.get("desconto") or 0.0), 2)
    if dados.get("vencimento") is None:
        produto_nome = dados.get("produto") or (plano.produto if plano else None)
        dias = _dias_do_produto(db, produto_nome, None, plano.dias if plano else None)
        dados["vencimento"] = date.today() + timedelta(days=dias)
    if plano:
        dados["plano_id"] = plano.id
        dados["plano_nome"] = dados.get("plano_nome") or plano.nome
        dados["produto"] = dados.get("produto") or plano.produto

    ass = Assinatura(**dados)
    ass.credenciais = [Credencial(**c.model_dump()) for c in payload.credenciais]
    ass.lucro = round(ass.valor_final - (ass.custo or 0.0), 2)

    db.add(ass)
    db.flush()
    registrar(db, "assinatura", ass.id, "criacao", depois=dados)

    # cliente ativo ja entra no "recebido no mes"
    if ass.status == "ATIVO" and (ass.valor_final or 0.0) > 0:
        db.add(Lancamento(
            assinatura_id=ass.id,
            tipo="pagamento",
            data=date.today(),
            valor=ass.valor_final,
            forma_pagamento=ass.forma_pagamento,
            plano_nome=ass.plano_nome,
            descricao="Pagamento inicial (automatico)",
        ))

    db.commit()
    db.refresh(ass)
    return ass


@router.patch("/{assinatura_id}", response_model=AssinaturaOut, summary="Atualizar assinatura")
def atualizar(assinatura_id: int, payload: AssinaturaUpdate, db: Session = Depends(get_db)):
    ass = _buscar(db, assinatura_id)
    dados = payload.model_dump(exclude_unset=True, exclude={"credenciais"})
    antes = {campo: getattr(ass, campo) for campo in dados}

    for campo, valor in dados.items():
        setattr(ass, campo, valor)

    if {"valor", "desconto"} & dados.keys() and "valor_final" not in dados:
        _recalcular(ass)
    if "custo" in dados and "valor_final" not in dados:
        ass.lucro = round((ass.valor_final or 0.0) - ass.custo, 2)

    if "plano_id" in dados or "plano_nome" in dados:
        if dados.get("plano_id") or dados.get("plano_nome"):
            plano = _resolver_plano(db, ass.plano_id, ass.plano_nome)
            if plano:
                ass.plano_id = plano.id
                ass.plano_nome = plano.nome
                ass.produto = plano.produto or ass.produto
        else:
            # permite deixar o cliente "sem plano" pelo painel
            ass.plano_id = None
            ass.plano_nome = None

    if payload.credenciais is not None:
        ass.credenciais.clear()
        ass.credenciais.extend(Credencial(**c.model_dump()) for c in payload.credenciais)

    if antes:
        registrar(db, "assinatura", ass.id, "atualizacao", antes=antes, depois=dados)
    db.commit()
    db.refresh(ass)
    return ass


@router.delete("/{assinatura_id}", response_model=AssinaturaOut, summary="Cancelar assinatura (soft delete)")
def cancelar(assinatura_id: int, db: Session = Depends(get_db)):
    ass = _buscar(db, assinatura_id)
    antes = {"status": ass.status}
    ass.status = "CANCELADO"
    registrar(db, "assinatura", ass.id, "cancelamento", antes=antes, depois={"status": ass.status})
    db.commit()
    db.refresh(ass)
    return ass


@router.post("/{assinatura_id}/renovar", response_model=PagamentoOut, summary="Renovar assinatura")
def renovar(assinatura_id: int, payload: RenovacaoIn, db: Session = Depends(get_db)):
    ass = _buscar(db, assinatura_id)
    hoje = date.today()
    vencimento_anterior = ass.vencimento

    plano = _resolver_plano(db, None, payload.plano_nome) or (ass.plano or _resolver_plano(db, ass.plano_id, ass.plano_nome))
    if payload.plano_nome and plano:
        ass.plano_id = plano.id
        ass.plano_nome = plano.nome
        ass.produto = plano.produto or ass.produto

    dias = _dias_do_produto(db, ass.produto, payload.dias, plano.dias if plano else None)
    valor = payload.valor if payload.valor is not None else (
        plano.valor if plano and payload.plano_nome else ass.valor_final
    )

    base = max(vencimento_anterior or hoje, hoje)
    novo_vencimento = base + timedelta(days=dias)

    ass.vencimento = novo_vencimento
    if ass.status != "CANCELADO" or payload.plano_nome:
        ass.status = "ATIVO"
    if payload.plano_nome and plano:
        ass.valor = plano.valor
        _recalcular(ass)
    if payload.forma_pagamento:
        ass.forma_pagamento = payload.forma_pagamento

    lancamento = Lancamento(
        assinatura_id=ass.id,
        tipo="renovacao",
        data=hoje,
        valor=valor or 0.0,
        forma_pagamento=payload.forma_pagamento or ass.forma_pagamento,
        plano_nome=ass.plano_nome,
        descricao=payload.observacao or f"Renovacao de {dias} dias",
    )
    db.add(lancamento)
    db.flush()
    registrar(
        db, "assinatura", ass.id, "renovacao",
        antes={"vencimento": vencimento_anterior},
        depois={"vencimento": novo_vencimento, "valor": valor},
    )
    db.commit()
    return {
        "assinatura_id": ass.id,
        "vencimento_anterior": vencimento_anterior,
        "vencimento_novo": novo_vencimento,
        "valor": valor or 0.0,
        "lancamento_id": lancamento.id,
    }


@router.post("/{assinatura_id}/pagamentos", response_model=LancamentoOut, status_code=201,
             summary="Registrar pagamento")
def registrar_pagamento(assinatura_id: int, payload: PagamentoIn, db: Session = Depends(get_db)):
    ass = _buscar(db, assinatura_id)
    lancamento = Lancamento(
        assinatura_id=ass.id,
        tipo="pagamento",
        data=payload.data or date.today(),
        valor=payload.valor,
        forma_pagamento=payload.forma_pagamento or ass.forma_pagamento,
        plano_nome=ass.plano_nome,
        descricao=payload.descricao,
    )
    db.add(lancamento)
    db.flush()
    registrar(db, "assinatura", ass.id, "pagamento", depois={"valor": payload.valor})
    db.commit()
    db.refresh(lancamento)
    return lancamento


@router.get("/{assinatura_id}/lancamentos", response_model=list[LancamentoOut],
            summary="Historico financeiro da assinatura")
def lancamentos(assinatura_id: int, db: Session = Depends(get_db)):
    _buscar(db, assinatura_id)
    return db.scalars(
        select(Lancamento)
        .where(Lancamento.assinatura_id == assinatura_id)
        .order_by(Lancamento.data.desc(), Lancamento.id.desc())
    ).all()


@router.post("/{assinatura_id}/suspender", response_model=AssinaturaOut, summary="Suspender")
def suspender(assinatura_id: int, db: Session = Depends(get_db)):
    ass = _buscar(db, assinatura_id)
    ass.status = "SUSPENSO"
    registrar(db, "assinatura", ass.id, "suspensao")
    db.commit()
    db.refresh(ass)
    return ass


@router.post("/{assinatura_id}/reativar", response_model=AssinaturaOut, summary="Reativar")
def reativar(assinatura_id: int, db: Session = Depends(get_db)):
    ass = _buscar(db, assinatura_id)
    ass.status = "ATIVO"
    registrar(db, "assinatura", ass.id, "reativacao")
    db.commit()
    db.refresh(ass)
    return ass
