from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..database import Base, get_db
from ..models import Produto
from ..security import verificar_api_key

router = APIRouter(prefix="/config-creditos", tags=["configuracao de creditos"])


class ConfigCredito(Base):
    __tablename__ = "config_creditos_produto"
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), primary_key=True)
    controlar_estoque: Mapped[bool] = mapped_column(Boolean, default=False)
    custo_credito: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    regra: Mapped[int] = mapped_column(Integer, default=0)
    reutilizavel: Mapped[bool] = mapped_column(Boolean, default=False)


REGRAS = {"nao_consumir": 0, "sempre": 1, "somente_30_dias": 2}


class ConfigIn(BaseModel):
    controlar_estoque: bool = False
    custo_credito: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    regra: Literal["nao_consumir", "sempre", "somente_30_dias"] = "nao_consumir"
    reutilizavel: bool = False

    @model_validator(mode="after")
    def validar(self):
        if not self.controlar_estoque and (self.regra != "nao_consumir" or self.reutilizavel):
            raise ValueError("Ative o estoque para configurar consumo ou reserva.")
        if self.regra == "sempre" and self.reutilizavel:
            raise ValueError("Credito sempre consumido nao pode ser reutilizavel.")
        return self


def buscar_produto(db, produto_id):
    produto = db.get(Produto, produto_id)
    if not produto:
        raise HTTPException(404, "Produto nao encontrado.")
    return produto


@router.get("/tela", include_in_schema=False, response_class=HTMLResponse)
def tela():
    return HTMLResponse(PAGINA)


@router.get("/{produto_id}", dependencies=[Depends(verificar_api_key)])
def ler(produto_id: int, db: Session = Depends(get_db)):
    produto = buscar_produto(db, produto_id)
    conf = db.get(ConfigCredito, produto_id)
    if not conf:
        nome = produto.nome.strip().casefold()
        return {"produto_id": produto_id, "controlar_estoque": nome in ("iptv", "internet"), "custo_credito": "0.00", "regra": "sempre" if nome == "iptv" else "somente_30_dias" if nome == "internet" else "nao_consumir", "reutilizavel": nome == "internet", "salvo": False}
    return {"produto_id": produto_id, "controlar_estoque": conf.controlar_estoque, "custo_credito": str(conf.custo_credito), "regra": next(k for k, v in REGRAS.items() if v == conf.regra), "reutilizavel": conf.reutilizavel, "salvo": True}


@router.put("/{produto_id}", dependencies=[Depends(verificar_api_key)])
def salvar(produto_id: int, payload: ConfigIn, db: Session = Depends(get_db)):
    buscar_produto(db, produto_id)
    conf = db.get(ConfigCredito, produto_id)
    if not conf:
        conf = ConfigCredito(produto_id=produto_id)
        db.add(conf)
    conf.controlar_estoque = payload.controlar_estoque
    conf.custo_credito = payload.custo_credito
    conf.regra = REGRAS[payload.regra]
    conf.reutilizavel = payload.reutilizavel
    db.commit()
    return ler(produto_id, db)


PAGINA = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Créditos por produto</title>
<style>body{background:#14102e;color:#eef0ff;font:16px system-ui;margin:24px auto;padding:16px;max-width:700px}label{display:block;margin:18px 0 6px}input,select,button{padding:10px;font:inherit;max-width:100%;box-sizing:border-box}select{width:100%}a{color:#abbcff}.nota{color:#b8b5ce}#mensagem{white-space:pre-wrap}</style>
<a href="/painel/produtos" target="_top">Voltar aos produtos</a><h1>Configurar créditos</h1>
<p class="nota">Esta etapa cadastra regras. Ainda não movimenta estoque nem gera despesas. Internet fora de 30 dias: sem custo; crédito reservado e reutilizável conforme configuração.</p>
<label>Produto<select id="produto"></select></label>
<label><input type="checkbox" id="estoque"> Controlar estoque</label>
<label>Custo por crédito (R$)<input id="custo" type="number" min="0" step="0.01" value="0"></label>
<label>Consumo<select id="regra"><option value="nao_consumir">Não consumir</option><option value="sempre">Consumir por venda/renovação</option><option value="somente_30_dias">Consumir somente em períodos de 30 dias</option></select></label>
<label><input type="checkbox" id="reutilizavel"> Reservar e liberar no vencimento quando não houver consumo</label>
<p><button id="salvar">Salvar configuração</button></p><p id="mensagem" role="status"></p>
<script>
const el=id=>document.getElementById(id);let carregado=false;
async function api(url,method='GET',body){const r=await fetch(url,{method,headers:{'X-API-Key':localStorage.getItem('assinaturas.apiKey')||'','Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));return d}
function dependencias(){const ativo=el('estoque').checked;el('regra').disabled=!ativo;el('reutilizavel').disabled=!ativo||el('regra').value==='sempre';if(!ativo)el('regra').value='nao_consumir';if(!ativo||el('regra').value==='sempre')el('reutilizavel').checked=false}
async function carregar(){carregado=false;el('salvar').disabled=true;try{const c=await api('/config-creditos/'+el('produto').value);el('estoque').checked=c.controlar_estoque;el('custo').value=c.custo_credito;el('regra').value=c.regra;el('reutilizavel').checked=c.reutilizavel;dependencias();el('mensagem').textContent=c.salvo?'Configuração salva.':'Sugestão inicial: confira e salve.';carregado=true}catch(e){el('mensagem').textContent=e.message}el('salvar').disabled=!carregado}
el('produto').onchange=carregar;el('estoque').onchange=dependencias;el('regra').onchange=dependencias;
el('salvar').onclick=async()=>{if(!carregado)return;el('salvar').disabled=true;try{await api('/config-creditos/'+el('produto').value,'PUT',{controlar_estoque:el('estoque').checked,custo_credito:el('custo').value,regra:el('regra').value,reutilizavel:el('reutilizavel').checked});el('mensagem').textContent='Configuração salva com sucesso.'}catch(e){el('mensagem').textContent=e.message}finally{el('salvar').disabled=false}};
(async()=>{try{const ps=await api('/produtos');for(const p of ps){const o=document.createElement('option');o.value=p.id;o.textContent=p.nome;el('produto').appendChild(o)}if(ps.length)await carregar();else{el('salvar').disabled=true;el('mensagem').textContent='Cadastre um produto primeiro.'}}catch(e){el('mensagem').textContent=e.message;el('salvar').disabled=true}})();
</script></html>'''
