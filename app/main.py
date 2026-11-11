from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from .config import API_KEY, APP_NAME, APP_VERSION, BASE_DIR
from .database import Base, engine
from .routers import admin, assinaturas, planos, produtos, relatorios, creditos_config

logger = logging.getLogger("api")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    produtos.preparar_dados()
    if API_KEY == "dev-local-troque-esta-chave":
        logger.warning("API_KEY padrao em uso. Defina a variavel de ambiente API_KEY.")
    yield

app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan, description="API local de assinaturas. Autentique com X-API-Key.")
for modulo in (assinaturas, planos, produtos, relatorios, admin, creditos_config):
    app.include_router(modulo.router)

@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok", "nome": APP_NAME, "versao": APP_VERSION}

@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/painel")

@app.get("/painel", include_in_schema=False)
def painel():
    html = (BASE_DIR / "web" / "painel.html").read_text(encoding="utf-8")
    botoes = '<a class="botao" href="/painel/produtos" style="text-decoration:none">Produtos</a> <a class="botao" href="/painel/planos" style="text-decoration:none">Planos</a> '
    return HTMLResponse(html.replace('<button id="btnAtualizar">', botoes + '<button id="btnAtualizar">', 1))

@app.get("/painel/produtos", include_in_schema=False)
@app.get("/painel/produtos/cadastro", include_in_schema=False)
def cadastro_produtos():
    return FileResponse(BASE_DIR / "web" / "produtos.html")

@app.get("/painel/planos", include_in_schema=False)
def tela_planos():
    return HTMLResponse(PLANOS_HTML)

PLANOS_HTML = '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Planos</title><style>*{box-sizing:border-box}body{background:#15102e;color:#eef0ff;font:15px system-ui;margin:0}main{max-width:1050px;margin:auto;padding:24px}a{color:#b6caff}.card{background:#241c49;border:1px solid #ffffff22;border-radius:16px;padding:22px;margin:20px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}label{display:block;margin:8px 0}input:not([type=checkbox]),select{width:100%;padding:11px;background:#17112f;color:white;border:1px solid #ffffff30;border-radius:8px;font:inherit}button{padding:10px 16px;margin:4px;background:#7957df;color:white;border:0;border-radius:8px;cursor:pointer}button:disabled{opacity:.5}td,th{padding:12px;text-align:left;border-bottom:1px solid #ffffff18}table{width:100%;border-collapse:collapse}.scroll{overflow:auto}.nota{color:#b7afce;line-height:1.6}#msg{white-space:pre-wrap}@media(max-width:600px){.grid{grid-template-columns:1fr}}</style></head><body><main><a href="/painel">Voltar ao painel</a> · <a href="/painel/produtos">Produtos</a><h1>Planos e preços</h1><p class="nota">O preço é cobrado do cliente. O custo do crédito é configurado em Produtos. Editar o plano não recalcula automaticamente assinaturas existentes.</p><button id="novo">+ Novo plano</button><button id="refresh">Atualizar lista</button><p id="msg" role="status"></p><section class="card"><div class="scroll"><table><thead><tr><th>Plano</th><th>Produto</th><th>Preço</th><th>Dias</th><th>Situação</th><th>Ação</th></tr></thead><tbody id="lista"></tbody></table></div></section><section class="card" id="form"><h2 id="titulo">Novo plano</h2><div class="grid"><div><label for="nome">Nome do plano</label><input id="nome" maxlength="80"></div><div><label for="produto">Produto</label><select id="produto"></select></div><div><label for="valor">Preço de venda</label><input id="valor" inputmode="numeric" value="R$ 0,00"><small>500 = R$ 5,00; 5000 = R$ 50,00.</small></div><div><label for="dias">Duração em dias</label><input id="dias" type="number" value="30" min="1" max="3650"></div><div><label for="conexoes">Conexões</label><input id="conexoes" type="number" value="1" min="1"></div></div><label><input id="ativo" type="checkbox" checked> Plano ativo</label><p class="nota">Produtos de duração fixa usam os dias configurados no produto para novas operações.</p><button id="salvar">Salvar plano</button><button id="cancelar">Cancelar</button></section></main><script>
const $=id=>document.getElementById(id);let id=null,centavos=0,ps=[],ocupado=false;const moeda=v=>Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});const aviso=t=>$('msg').textContent=t;
async function api(url,method='GET',body){const r=await fetch(url,{method,headers:{'Content-Type':'application/json','X-API-Key':localStorage.getItem('assinaturas.apiKey')||''},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));return d}
function travar(v){ocupado=v;document.querySelectorAll('button').forEach(b=>b.disabled=v)}
function duracao(){const p=ps.find(p=>p.nome===$('produto').value);$('dias').disabled=!!p?.duracao_fixa;if(p?.duracao_fixa)$('dias').value=p.dias}
function limpar(){id=null;centavos=0;$('titulo').textContent='Novo plano';$('nome').value='';$('valor').value=moeda(0);$('dias').value=30;$('conexoes').value=1;$('ativo').checked=true;$('produto').selectedIndex=0;duracao()}
async function listar(){const planos=await api('/planos');$('lista').replaceChildren();for(const p of planos){const tr=document.createElement('tr');for(const t of [p.nome,p.produto||'Sem produto',moeda(p.valor),p.dias,p.ativo?'Ativo':'Inativo']){const td=document.createElement('td');td.textContent=t;tr.appendChild(td)}const td=document.createElement('td'),b=document.createElement('button');b.textContent='Editar';b.onclick=()=>{if(ocupado)return;id=p.id;$('titulo').textContent='Editar plano';$('nome').value=p.nome;if(p.produto&&!Array.from($('produto').options).some(o=>o.value===p.produto)){const o=document.createElement('option');o.value=p.produto;o.textContent=p.produto+' (legado)';$('produto').appendChild(o)}$('produto').value=p.produto||'';centavos=Math.round(p.valor*100);$('valor').value=moeda(centavos/100);$('dias').value=p.dias;$('conexoes').value=p.conexoes;$('ativo').checked=p.ativo;duracao();$('form').scrollIntoView({behavior:'smooth'})};td.appendChild(b);tr.appendChild(td);$('lista').appendChild(tr)}}
$('valor').oninput=()=>{centavos=Number($('valor').value.replace(/[^0-9]/g,'')||0);$('valor').value=moeda(centavos/100)};$('produto').onchange=duracao;$('novo').onclick=$('cancelar').onclick=()=>{if(!ocupado)limpar()};
$('salvar').onclick=async()=>{if(ocupado)return;const nome=$('nome').value.trim(),dias=Number($('dias').value),conexoes=Number($('conexoes').value);if(!nome||!Number.isInteger(dias)||dias<1||dias>3650||!Number.isInteger(conexoes)||conexoes<1||!Number.isSafeInteger(centavos)||centavos<0||centavos>999999999999){aviso('Confira nome, preço, dias e conexões.');return}const payload={nome,produto:$('produto').value||null,valor:centavos/100,dias,conexoes,ativo:$('ativo').checked};travar(true);try{await api(id?'/planos/'+id:'/planos',id?'PATCH':'POST',payload);await listar();limpar();aviso('Plano salvo. Clientes antigos mantêm seus valores atuais.')}catch(e){aviso(e.message)}finally{travar(false)}};
$('refresh').onclick=async()=>{if(ocupado)return;travar(true);try{await listar()}catch(e){aviso(e.message)}finally{travar(false)}};
(async()=>{travar(true);try{ps=await api('/produtos');const vazio=document.createElement('option');vazio.value='';vazio.textContent='Sem produto';$('produto').appendChild(vazio);for(const p of ps){const o=document.createElement('option');o.value=p.nome;o.textContent=p.nome+(p.ativo?'':' (inativo)');$('produto').appendChild(o)}await listar();limpar()}catch(e){aviso(e.message)}finally{travar(false)}})();
</script></body></html>'''
