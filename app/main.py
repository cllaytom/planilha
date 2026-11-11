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


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan,
    description="API local de assinaturas. Autentique com X-API-Key.")
app.include_router(assinaturas.router)
app.include_router(planos.router)
app.include_router(produtos.router)
app.include_router(relatorios.router)
app.include_router(admin.router)
app.include_router(creditos_config.router)


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok", "nome": APP_NAME, "versao": APP_VERSION}


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/painel")


@app.get("/painel", include_in_schema=False)
def painel():
    html = (BASE_DIR / "web" / "painel.html").read_text(encoding="utf-8")
    botao = '<a class="botao" href="/painel/produtos" style="text-decoration:none">Produtos</a>\n    '
    return HTMLResponse(html.replace('<button id="btnAtualizar">', botao + '<button id="btnAtualizar">', 1))


@app.get("/painel/produtos", include_in_schema=False)
def painel_produtos():
    return HTMLResponse('''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Produtos</title><body style="margin:0;background:#14102e;color:white;font-family:system-ui"><nav style="padding:16px"><a style="color:#b9c8ff" href="/painel">Painel</a> · <a style="color:#b9c8ff" href="/config-creditos/tela">Configurar créditos e regras por produto</a><p>Após cadastrar um produto, abra as configurações de créditos para definir suas regras.</p></nav><iframe title="Cadastro de produtos" src="/painel/produtos/cadastro" style="width:100%;height:85vh;border:0"></iframe></body></html>''')


@app.get("/painel/produtos/cadastro", include_in_schema=False)
def cadastro_produtos():
    return FileResponse(BASE_DIR / "web" / "produtos.html")
