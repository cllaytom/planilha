from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auditoria import registrar
from ..database import get_db
from ..models import Assinatura, Plano
from ..schemas import PlanoCreate, PlanoOut, PlanoUpdate
from ..security import verificar_api_key

router = APIRouter(prefix="/planos", tags=["planos"], dependencies=[Depends(verificar_api_key)])


@router.get("", response_model=list[PlanoOut], summary="Listar planos")
def listar(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    stmt = select(Plano).order_by(Plano.nome)
    if apenas_ativos:
        stmt = stmt.where(Plano.ativo.is_(True))
    return db.scalars(stmt).all()


@router.get("/{plano_id}", response_model=PlanoOut, summary="Detalhar plano")
def detalhar(plano_id: int, db: Session = Depends(get_db)):
    plano = db.get(Plano, plano_id)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano nao encontrado.")
    return plano


@router.post("", response_model=PlanoOut, status_code=201, summary="Criar plano")
def criar(payload: PlanoCreate, db: Session = Depends(get_db)):
    existe = db.scalar(select(Plano).where(func.upper(Plano.nome) == payload.nome.upper()))
    if existe:
        raise HTTPException(status_code=409, detail=f"Ja existe um plano com o nome '{payload.nome}'.")
    plano = Plano(**payload.model_dump())
    db.add(plano)
    db.flush()
    registrar(db, "plano", plano.id, "criacao", depois=payload.model_dump())
    db.commit()
    db.refresh(plano)
    return plano


@router.patch("/{plano_id}", response_model=PlanoOut, summary="Atualizar plano")
def atualizar(plano_id: int, payload: PlanoUpdate, db: Session = Depends(get_db)):
    plano = db.get(Plano, plano_id)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano nao encontrado.")
    dados = payload.model_dump(exclude_unset=True)
    antes = {campo: getattr(plano, campo) for campo in dados}
    for campo, valor in dados.items():
        setattr(plano, campo, valor)
    registrar(db, "plano", plano.id, "atualizacao", antes=antes, depois=dados)
    db.commit()
    db.refresh(plano)
    return plano


@router.delete("/{plano_id}", status_code=204, summary="Desativar plano")
def desativar(plano_id: int, db: Session = Depends(get_db)):
    plano = db.get(Plano, plano_id)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano nao encontrado.")
    em_uso = db.scalar(
        select(func.count(Assinatura.id)).where(Assinatura.plano_id == plano_id)
    )
    if em_uso:
        raise HTTPException(
            status_code=409,
            detail=f"Plano em uso por {em_uso} assinatura(s). Desative com PATCH ativo=false.",
        )
    db.delete(plano)
    registrar(db, "plano", plano_id, "exclusao")
    db.commit()
