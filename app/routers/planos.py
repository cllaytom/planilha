from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auditoria import registrar
from ..database import get_db
from ..models import Assinatura, Plano, Produto
from ..regras_planos import validar_campos
from ..schemas import PlanoCreate, PlanoOut, PlanoUpdate
from ..security import verificar_api_key

router = APIRouter(prefix='/planos', tags=['planos'], dependencies=[Depends(verificar_api_key)])


def buscar(db, plano_id):
    plano = db.get(Plano, plano_id)
    if plano is None:
        raise HTTPException(404, 'Plano nao encontrado.')
    return plano


def preparar(db, dados, atual=None):
    try:
        d = validar_campos(dados)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if 'nome' in d:
        stmt = select(Plano.id).where(func.upper(func.trim(Plano.nome)) == d['nome'].upper())
        if atual is not None:
            stmt = stmt.where(Plano.id != atual.id)
        if db.scalar(stmt) is not None:
            raise HTTPException(409, 'Ja existe um plano com esse nome, inclusive entre os arquivados. Edite ou reative o existente.')
    precisa_produto = atual is None or 'produto' in d or (d.get('ativo') is True and not atual.ativo)
    if precisa_produto:
        nome = d.get('produto', atual.produto if atual else None)
        produto = db.scalar(select(Produto).where(func.upper(func.trim(Produto.nome)) == (nome or '').strip().upper())) if nome else None
        if produto is None:
            raise HTTPException(422, 'Selecione um produto cadastrado para este plano.')
        if not produto.ativo:
            raise HTTPException(422, 'O produto esta arquivado. Reative-o antes de vincular o plano.')
        d['produto'] = produto.nome
        if produto.duracao_fixa:
            d['dias'] = produto.dias
    return d


def salvar(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Conflito ao salvar. Confira nome duplicado e vinculos do plano.') from exc


@router.get('', response_model=list[PlanoOut])
def listar(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    stmt = select(Plano).order_by(Plano.nome)
    if apenas_ativos:
        stmt = stmt.where(Plano.ativo.is_(True))
    return db.scalars(stmt).all()


@router.get('/{plano_id}', response_model=PlanoOut)
def detalhar(plano_id: int, db: Session = Depends(get_db)):
    return buscar(db, plano_id)


@router.post('', response_model=PlanoOut, status_code=201)
def criar(payload: PlanoCreate, db: Session = Depends(get_db)):
    dados = preparar(db, payload.model_dump())
    plano = Plano(**dados)
    db.add(plano)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Ja existe um plano com esse nome.') from exc
    registrar(db, 'plano', plano.id, 'criacao', depois=dados)
    salvar(db)
    db.refresh(plano)
    return plano


@router.patch('/{plano_id}', response_model=PlanoOut)
def atualizar(plano_id: int, payload: PlanoUpdate, db: Session = Depends(get_db)):
    plano = buscar(db, plano_id)
    dados = preparar(db, payload.model_dump(exclude_unset=True), plano)
    antes = {k: getattr(plano, k) for k in dados}
    for k, v in dados.items():
        setattr(plano, k, v)
    registrar(db, 'plano', plano.id, 'atualizacao', antes=antes, depois=dados)
    salvar(db)
    db.refresh(plano)
    return plano


@router.delete('/{plano_id}', status_code=204)
def excluir(plano_id: int, db: Session = Depends(get_db)):
    plano = buscar(db, plano_id)
    # Importados podem ter apenas o nome, sem plano_id.
    em_uso = db.scalar(select(func.count(Assinatura.id)).where(or_(
        Assinatura.plano_id == plano.id,
        func.upper(func.trim(Assinatura.plano_nome)) == plano.nome.strip().upper(),
    )))
    if em_uso:
        raise HTTPException(409, f'Plano vinculado a {em_uso} cliente(s). Arquive com ativo=false; clientes e vencimentos serao preservados.')
    registrar(db, 'plano', plano.id, 'exclusao', antes={'nome': plano.nome})
    db.delete(plano)
    salvar(db)
