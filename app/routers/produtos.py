from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from ..auditoria import registrar
from ..database import SessionLocal, get_db
from ..models import Assinatura, Lancamento, Produto
from ..routers.creditos_config import ConfigCredito
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


class ProdutoComCusto(BaseModel):
    nome: str
    duracao_fixa: bool = False
    dias: int = 30
    custo_ativacao: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)


@router.get("", response_model=list[ProdutoOut], summary="Listar produtos")
def listar(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    stmt = select(Produto).order_by(Produto.nome)
    if apenas_ativos:
        stmt = stmt.where(Produto.ativo.is_(True))
    return db.scalars(stmt).all()


@router.post("", response_model=ProdutoOut, status_code=201, summary="Criar produto")
def criar(payload: ProdutoComCusto, db: Session = Depends(get_db)):
    existe = db.scalar(select(Produto).where(func.upper(Produto.nome) == payload.nome.strip().upper()))
    if existe:
        raise HTTPException(status_code=409, detail=f"Ja existe um produto '{payload.nome}'.")

    dados = payload.model_dump(exclude={"custo_ativacao"})
    produto = Produto(**dados)
    produto.nome = produto.nome.strip()
    db.add(produto)
    db.flush()

    nome = produto.nome.strip().casefold()
    regra = 2 if nome == "internet" else 1
    config = ConfigCredito(
        produto_id=produto.id,
        controlar_estoque=True,
        custo_credito=payload.custo_ativacao,
        regra=regra,
        reutilizavel=nome == "internet",
    )
    db.add(config)

    registrar(db, "produto", produto.id, "criacao", depois={**dados, "custo_ativacao": str(payload.custo_ativacao)})
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


@router.delete("/{produto_id}", response_model=ProdutoOut, summary="Excluir produto permanentemente")
def excluir(produto_id: int, db: Session = Depends(get_db)):
    produto = db.get(Produto, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto nao encontrado.")

    config = db.get(ConfigCredito, produto.id)
    if config:
        db.delete(config)

    dados = {
        "id": produto.id,
        "nome": produto.nome,
        "duracao_fixa": produto.duracao_fixa,
        "dias": produto.dias,
        "ativo": produto.ativo,
    }
    registrar(db, "produto", produto.id, "exclusao", antes=dados)
    db.delete(produto)
    db.commit()
    return produto


@router.get("/tela", include_in_schema=False, response_class=HTMLResponse)
def tela():
    return HTMLResponse(PAGINA)


PAGINA = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Produtos</title>
<style>body{background:#14102e;color:#eef0ff;font:16px system-ui;margin:24px auto;padding:16px;max-width:760px}label{display:block;margin:14px 0 6px}input,select,button{padding:10px;font:inherit;max-width:100%;box-sizing:border-box}table{width:100%;border-collapse:collapse;margin-top:18px}th,td{padding:10px;border-bottom:1px solid #332a5c;text-align:left}a{color:#abbcff}.acao{color:#ff8080;background:none;border:none;cursor:pointer;font:inherit}.nota{color:#b8b5ce}#mensagem{white-space:pre-wrap}</style>
<a href="/painel" target="_top">Voltar</a><h1>Produtos</h1>
<p class="nota">O custo informado sera cobrado como despesa a cada ativacao ou renovacao de 30 dias. Nao altera clientes ou lancamentos anteriores.</p>
<label>Nome<input id="nome" placeholder="Ex.: IPTV"></label>
<label>Custo por ativacao (R$)<input id="custo" type="number" min="0" step="0.01" value="0"></label>
<label><input type="checkbox" id="fixa"> Duracao fixa</label>
<label>Dias<input id="dias" type="number" min="1" value="30"></label>
<p><button id="criar">Criar produto</button></p><p id="mensagem" role="status"></p>
<table><thead><tr><th>Produto</th><th>Duracao</th><th>Custo por ativacao</th><th></th></tr></thead><tbody id="lista"></tbody></table>
<script>
const el=id=>document.getElementById(id);
async function api(url,method='GET',body){const r=await fetch(url,{method,headers:{'X-API-Key':localStorage.getItem('assinaturas.apiKey')||'','Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));return d}
async function carregar(){el('lista').innerHTML='';try{const ps=await api('/produtos');for(const p of ps){let custo='0,00';try{const c=await api('/config-creditos/'+p.id);custo=Number(c.custo_credito).toLocaleString('pt-BR',{minimumFractionDigits:2})}catch(e){}
const tr=document.createElement('tr');tr.innerHTML=`<td>${p.nome}</td><td>${p.duracao_fixa?p.dias+' dias':'flexivel'}</td><td>R$ ${custo}</td><td><button class="acao" data-id="${p.id}">Excluir</button></td>`;el('lista').appendChild(tr)}
document.querySelectorAll('.acao').forEach(b=>b.onclick=async()=>{if(!confirm('Excluir este produto permanentemente? Clientes e lancamentos anteriores nao serao alterados.'))return;try{await api('/produtos/'+b.dataset.id,'DELETE');await carregar();el('mensagem').textContent='Produto excluido.'}catch(e){el('mensagem').textContent=e.message}})}catch(e){el('mensagem').textContent=e.message}}
el('criar').onclick=async()=>{try{await api('/produtos','POST',{nome:el('nome').value,duracao_fixa:el('fixa').checked,dias:Number(el('dias').value||30),custo_ativacao:el('custo').value||0});el('nome').value='';el('custo').value='0';await carregar();el('mensagem').textContent='Produto criado.'}catch(e){el('mensagem').textContent=e.message}};
(async()=>{await carregar()})();
</script></html>'''
