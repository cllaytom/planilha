from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from .config import API_KEY, APP_NAME, APP_VERSION, BASE_DIR
from .database import Base, engine
from .routers import admin, assinaturas, planos, produtos, relatorios

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    produtos.preparar_dados()
    if API_KEY == "dev-local-troque-esta-chave":
        logger.warning("API_KEY padrao em uso. Defina a variavel de ambiente API_KEY.")
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
    description=(
        "API para um agente de IA gerenciar a base de assinaturas: clientes, planos, "
        "vencimentos, renovacoes, pagamentos e despesas.\n\n"
        "Autentique com o header **X-API-Key**."
    ),
)

app.include_router(assinaturas.router)
app.include_router(planos.router)
app.include_router(produtos.router)
app.include_router(relatorios.router)
app.include_router(admin.router)


@app.get("/health", tags=["sistema"], summary="Verificacao de saude")
def health():
    return {"status": "ok", "nome": APP_NAME, "versao": APP_VERSION}


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/painel")


@app.get("/painel", include_in_schema=False)
def painel():
    html = (BASE_DIR / "web" / "painel.html").read_text(encoding="utf-8")
    botao = '<a class="botao" href="/painel/produtos" style="text-decoration:none">Produtos</a>\n    '
    html = html.replace('<button id="btnAtualizar">', botao + '<button id="btnAtualizar">', 1)
    return HTMLResponse(html)


@app.get("/painel/produtos", include_in_schema=False)
def painel_produtos():
    return FileResponse(BASE_DIR / "web" / "produtos.html")
