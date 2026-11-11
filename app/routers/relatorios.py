from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auditoria import registrar
from ..database import get_db
from ..models import Assinatura, Evento, Lancamento
from ..schemas import Dashboard, LancamentoCreate, LancamentoOut, Pagina
from ..security import verificar_api_key

router = APIRouter(tags=["relatorios"], dependencies=[Depends(verificar_api_key)])

STATUS_EM_DIA = ["ATIVO", "TESTE"]


@router.get("/dashboard", response_model=Dashboard, summary="Resumo geral do negocio")
def dashboard(db: Session = Depends(get_db)):
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    def contar(condicoes) -> int:
        return db.scalar(select(func.count(Assinatura.id)).where(*condicoes)) or 0

    em_dia = Assinatura.status.in_(STATUS_EM_DIA)
    total = db.scalar(select(func.count(Assinatura.id))) or 0

    mrr = db.scalar(
        select(func.coalesce(func.sum(Assinatura.valor_final), 0.0)).where(em_dia)
    ) or 0.0

    carteira = db.scalar(
        select(func.coalesce(func.sum(Assinatura.valor_final), 0.0)).where(
            Assinatura.status != "CANCELADO"
        )
    ) or 0.0

    recebido = db.scalar(
        select(func.coalesce(func.sum(Lancamento.valor), 0.0)).where(
            Lancamento.tipo.in_(["renovacao", "pagamento"]),
            Lancamento.data >= inicio_mes,
        )
    ) or 0.0

    despesas = db.scalar(
        select(func.coalesce(func.sum(Lancamento.valor), 0.0)).where(
            Lancamento.tipo == "despesa", Lancamento.data >= inicio_mes
        )
    ) or 0.0

    por_produto = {
        (nome or "SEM PRODUTO"): qtd
        for nome, qtd in db.execute(
            select(Assinatura.produto, func.count(Assinatura.id)).group_by(Assinatura.produto)
        ).all()
    }
    por_plano = {
        (nome or "SEM PLANO"): qtd
        for nome, qtd in db.execute(
            select(Assinatura.plano_nome, func.count(Assinatura.id)).group_by(Assinatura.plano_nome)
        ).all()
    }

    return {
        "hoje": hoje,
        "total": total,
        "ativas": contar([Assinatura.status == "ATIVO"]),
        "inativas": contar([Assinatura.status == "INATIVO"]),
        "suspensas": contar([Assinatura.status == "SUSPENSO"]),
        "canceladas": contar([Assinatura.status == "CANCELADO"]),
        "vencidas": contar([em_dia, Assinatura.vencimento < hoje]),
        "vencidas_por_data": contar([
            Assinatura.status != "CANCELADO", Assinatura.vencimento < hoje
        ]),
        "vencendo_7_dias": contar([
            em_dia, Assinatura.vencimento.between(hoje, hoje + timedelta(days=7))
        ]),
        "mrr": round(float(mrr), 2),
        "valor_carteira": round(float(carteira), 2),
        "recebido_mes": round(float(recebido), 2),
        "despesas_mes": round(float(despesas), 2),
        "lucro_mes": round(float(recebido) - float(despesas), 2),
        "por_produto": por_produto,
        "por_plano": por_plano,
    }


@router.get("/vencimentos", response_model=list, summary="Assinaturas que vencem nos proximos N dias")
def vencimentos(
    dias: int = Query(default=7, ge=0, le=365),
    incluir_atrasadas: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    hoje = date.today()
    stmt = (
        select(Assinatura)
        .where(Assinatura.status.in_(STATUS_EM_DIA))
        .where(Assinatura.vencimento <= hoje + timedelta(days=dias))
    )
    if not incluir_atrasadas:
        stmt = stmt.where(Assinatura.vencimento >= hoje)
    assinaturas = db.scalars(stmt.order_by(Assinatura.vencimento)).all()
    return [
        {
            "id": a.id,
            "nome": a.nome,
            "contato": a.contato,
            "plano": a.plano_nome,
            "valor_final": a.valor_final,
            "vencimento": a.vencimento,
            "situacao": a.situacao,
            "dias_atraso": a.dias_atraso,
        }
        for a in assinaturas
    ]


@router.get("/inadimplentes", response_model=list, summary="Assinaturas vencidas e ativas")
def inadimplentes(
    limite: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    hoje = date.today()
    assinaturas = db.scalars(
        select(Assinatura)
        .where(Assinatura.status.in_(STATUS_EM_DIA))
        .where(Assinatura.vencimento < hoje)
        .order_by(Assinatura.vencimento)
        .limit(limite)
    ).all()
    return [
        {
            "id": a.id,
            "nome": a.nome,
            "usuario": a.usuario,
            "contato": a.contato,
            "plano": a.plano_nome,
            "valor_final": a.valor_final,
            "vencimento": a.vencimento,
            "dias_atraso": a.dias_atraso,
        }
        for a in assinaturas
    ]


@router.get("/lancamentos", response_model=Pagina[LancamentoOut], summary="Listar lancamentos financeiros")
def listar_lancamentos(
    tipo: str | None = Query(default=None, description="renovacao | pagamento | despesa | estorno"),
    de: date | None = None,
    ate: date | None = None,
    limite: int = Query(default=100, ge=1, le=500),
    deslocamento: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Lancamento)
    if tipo:
        stmt = stmt.where(Lancamento.tipo == tipo.strip().lower())
    if de:
        stmt = stmt.where(Lancamento.data >= de)
    if ate:
        stmt = stmt.where(Lancamento.data <= ate)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    itens = db.scalars(
        stmt.order_by(Lancamento.data.desc(), Lancamento.id.desc())
        .limit(limite).offset(deslocamento)
    ).all()
    return {"total": total, "itens": itens}


@router.post("/lancamentos", response_model=LancamentoOut, status_code=201,
             summary="Criar lancamento (pagamento avulso ou despesa)")
def criar_lancamento(payload: LancamentoCreate, db: Session = Depends(get_db)):
    lancamento = Lancamento(**payload.model_dump(exclude={"data"}), data=payload.data or date.today())
    db.add(lancamento)
    db.flush()
    registrar(db, "lancamento", lancamento.id, "criacao", depois=payload.model_dump())
    db.commit()
    db.refresh(lancamento)
    return lancamento


@router.delete("/lancamentos/{lancamento_id}", status_code=204, summary="Excluir lancamento")
def excluir_lancamento(lancamento_id: int, db: Session = Depends(get_db)):
    lancamento = db.get(Lancamento, lancamento_id)
    if not lancamento:
        raise HTTPException(status_code=404, detail="Lancamento nao encontrado.")
    registrar(db, "lancamento", lancamento.id, "exclusao",
              antes={"tipo": lancamento.tipo, "valor": lancamento.valor})
    db.delete(lancamento)
    db.commit()


@router.get("/eventos", response_model=Pagina[dict], summary="Auditoria das alteracoes")
def eventos(
    entidade: str | None = None,
    limite: int = Query(default=100, ge=1, le=500),
    deslocamento: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Evento)
    if entidade:
        stmt = stmt.where(Evento.entidade == entidade)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    itens = db.scalars(
        stmt.order_by(Evento.id.desc()).limit(limite).offset(deslocamento)
    ).all()
    return {
        "total": total,
        "itens": [
            {
                "id": e.id,
                "entidade": e.entidade,
                "entidade_id": e.entidade_id,
                "acao": e.acao,
                "antes": e.antes,
                "depois": e.depois,
                "origem": e.origem,
                "criado_em": e.criado_em,
            }
            for e in itens
        ],
    }
