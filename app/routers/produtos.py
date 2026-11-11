from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from ..auditoria import registrar
from ..database import SessionLocal, get_db
from ..models import Assinatura, Lancamento, Produto
from ..schemas import ProdutoCreate, ProdutoOut, ProdutoUpdate
from ..security import verificar_api_key

router = APIRouter(prefix="/produtos", tags=["produtos"], dependencies=[Depends(verificar_api_key)])

# (nome, duracao_fixa, dias)
PRODUTOS_PADRAO = [("IPTV", True, 30), ("Internet", False, 30)]


def preparar_dados() -> None:
    """Roda ao iniciar: cria IPTV/Internet e lanca o pagamento de clientes ativos sem nenhum lancamento."""
    hoje = date.today()
    with SessionLocal() as db:
        for nome, fixa, dias in PRODUTOS_PADRAO:
            existe = db.scalar(select(Produto).where(func.upper(Produto.nome) == nome.upper()))
            if not existe:
                db.add(Produto(nome=nome, duracao_fixa=fixa, dias=dias))

        sem_lancamento = ~exists().where(Lancamento.assinatura_id == Assinatura.id)
        pendentes = db.scalars(
            select(Assinatura).where(
                Assinatura.status == "ATIVO",
                Assinatura.valor_final > 0,
                Assinatura.vencimento >= hoje,
                sem_lancamento,
            )
        ).all()
        for ass in pendentes:
            db.add(Lancamento(
                assinatura_id=ass.id,
                tipo="pagamento",
                data=max(ass.data_cadastro or hoje, hoje.replace(day=1)),
                valor=ass.valor_final,
                forma_pagamento=ass.forma_pagamento,
                plano_nome=ass.plano_nome,
                descricao="Pagamento inicial (automatico)",
            ))
        db.commit()


@router.get("", response_model=list[ProdutoOut], summary="Listar produtos")
def listar(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    stmt = select(Produto).order_by(Produto.nome)
    if apenas_ativos:
        stmt = stmt.where(Produto.ativo.is_(True))
    return db.scalars(stmt).all()


@router.post("", response_model=ProdutoOut, status_code=201, summary="Criar produto")
def criar(payload: ProdutoCreate, db: Session = Depends(get_db)):
    existe = db.scalar(select(Produto).where(func.upper(Produto.nome) == payload.nome.strip().upper()))
    if existe:
        raise HTTPException(status_code=409, detail=f"Ja existe um produto '{payload.nome}'.")
    produto = Produto(**payload.model_dump())
    produto.nome = produto.nome.strip()
    db.add(produto)
    db.flush()
    registrar(db, "produto", produto.id, "criacao", depois=payload.model_dump())
    db.commit()
    db.refresh(produto)
    return produto


@router.patch("/{produto_id}", response_model=ProdutoOut, summary="Atualizar produto")
def atualizar(produto_id: int, payload: ProdutoUpdate, db: Session = Depends(get_db)):
    produto = db.get(Produto, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto nao encontrado.")
    dados = payload.model_dump(exclude_unset=True)
    antes = {campo: getattr(produto, campo) for campo in dados}
    for campo, valor in dados.items():
        setattr(produto, campo, valor)
    registrar(db, "produto", produto.id, "atualizacao", antes=antes, depois=dados)
    db.commit()
    db.refresh(produto)
    return produto


@router.delete("/{produto_id}", response_model=ProdutoOut, summary="Desativar produto")
def desativar(produto_id: int, db: Session = Depends(get_db)):
    produto = db.get(Produto, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto nao encontrado.")
    produto.ativo = False
    registrar(db, "produto", produto.id, "desativacao")
    db.commit()
    db.refresh(produto)
    return produto
