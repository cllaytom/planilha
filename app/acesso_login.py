import hashlib
import json
import re
import secrets
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, delete, func, select
from starlette.middleware.base import BaseHTTPMiddleware

from .acesso_regras import conferir, hash_senha, permitido
from .config import BASE_DIR
from .database import Base, SessionLocal, engine
from .models import Evento, Plano, Produto

COOKIE = 'assinaturas_sessao'
DURACAO = 8 * 60 * 60
router = APIRouter()


class Conta(Base):
    __tablename__ = 'acesso_contas'
    id = Column(Integer, primary_key=True)
    login = Column(String(40), unique=True, nullable=False)
    nome = Column(String(100), nullable=False)
    senha_hash = Column(Text, nullable=False)
    papel = Column(String(10), nullable=False, default='usuario')
    ativo = Column(Boolean, nullable=False, default=True)
    trocar_senha = Column(Boolean, nullable=False, default=True)


class Sessao(Base):
    __tablename__ = 'acesso_sessoes'
    token_hash = Column(String(64), primary_key=True)
    conta_id = Column(Integer, ForeignKey('acesso_contas.id'), nullable=False)
    expira = Column(Integer, nullable=False)


class Tentativa(Base):
    __tablename__ = 'acesso_tentativas'
    chave = Column(String(64), primary_key=True)
    inicio = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False, default=0)


def publico(u):
    return {'id': u.id, 'login': u.login, 'nome': u.nome, 'papel': u.papel,
            'ativo': u.ativo, 'trocar_senha': u.trocar_senha}


def resumo_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def identificar(request):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 200:
        return None
    with SessionLocal() as db:
        s = db.get(Sessao, resumo_token(token))
        if not s or s.expira <= int(time.time()):
            return None
        u = db.get(Conta, s.conta_id)
        return publico(u) if u and u.ativo else None


def autenticar(request):
    u = getattr(request.state, 'identidade', None)
    if not u:
        raise HTTPException(401, 'Entre com login e senha.')
    return u


async def verificar_api_key(request: Request):
    u = autenticar(request)
    if u['papel'] == 'usuario' and request.method in ('POST', 'PATCH') and request.url.path.rstrip('/') == '/assinaturas' or (u['papel'] == 'usuario' and request.method == 'PATCH' and re.fullmatch(r'/assinaturas/\d+', request.url.path.rstrip('/'))):
        dados = await request.json()
        campos = {'nome', 'usuario', 'contato', 'status', 'produto', 'plano_id', 'plano_nome', 'valor', 'conexoes', 'desconto', 'vencimento', 'observacao', 'forma_pagamento', 'credenciais'}
        if not isinstance(dados, dict) or set(dados) - campos:
            raise HTTPException(403, 'Campo nao permitido para este perfil.')
        if dados.get('status') == 'CANCELADO':
            raise HTTPException(403, 'Somente administrador pode cancelar clientes.')


def registrar(db, u, acao, alvo=None):
    db.add(Evento(entidade='acesso', entidade_id=alvo, acao=acao,
                  origem='usuario:' + str(u['id']) if u else 'instalacao'))


def criar_sessao(db, conta_id):
    token = secrets.token_urlsafe(32)
    db.add(Sessao(token_hash=resumo_token(token), conta_id=conta_id, expira=int(time.time()) + DURACAO))
    db.execute(delete(Sessao).where(Sessao.expira < int(time.time())))
    return token


def cookie(response, request, token):
    response.set_cookie(COOKIE, token, httponly=True, secure=request.url.scheme == 'https',
                        samesite='strict', max_age=DURACAO, path='/')
    return response


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=40)
    senha: str = Field(min_length=1, max_length=128)


class SenhaIn(BaseModel):
    atual: str = Field(min_length=1, max_length=128)
    nova: str = Field(min_length=12, max_length=128)


class ContaIn(BaseModel):
    login: str = Field(min_length=3, max_length=40)
    nome: str = Field(min_length=1, max_length=100)
    senha: str = Field(min_length=12, max_length=128)
    papel: str = 'usuario'


class ContaUpdate(BaseModel):
    ativo: bool | None = None
    papel: str | None = None
    senha: str | None = Field(default=None, min_length=12, max_length=128)


@router.post('/auth/login')
def login(payload: LoginIn, request: Request):
    agora = int(time.time())
    chave = resumo_token(request.client.host if request.client else 'local')
    with SessionLocal() as db:
        tent = db.get(Tentativa, chave)
        if tent and agora - tent.inicio < 900 and tent.total >= 10:
            raise HTTPException(429, 'Muitas tentativas. Aguarde 15 minutos.')
        u = db.scalar(select(Conta).where(Conta.login == payload.login.strip().lower()))
        valido = conferir(payload.senha, u.senha_hash if u else HASH_FALSO)
        if not u or not u.ativo or not valido:
            if not tent:
                tent = Tentativa(chave=chave, inicio=agora, total=0)
                db.add(tent)
            if agora - tent.inicio >= 900:
                tent.inicio, tent.total = agora, 0
            tent.total += 1
            db.commit()
            raise HTTPException(401, 'Login ou senha invalidos.')
        if u.login == 'admin' and u.trocar_senha and payload.senha == 'admin' and request.client and request.client.host not in ('127.0.0.1', '::1', 'testclient'):
            raise HTTPException(403, 'Configure a senha inicial no proprio computador do painel.')
        if tent:
            tent.total = 0
        velho = request.cookies.get(COOKIE)
        if velho:
            db.execute(delete(Sessao).where(Sessao.token_hash == resumo_token(velho)))
        token = criar_sessao(db, u.id)
        registrar(db, publico(u), 'login', u.id)
        dados = publico(u)
        db.commit()
    return cookie(JSONResponse(dados), request, token)


@router.get('/auth/me')
def me(request: Request):
    return autenticar(request)


@router.post('/auth/logout')
def logout(request: Request):
    token = request.cookies.get(COOKIE, '')
    with SessionLocal() as db:
        db.execute(delete(Sessao).where(Sessao.token_hash == resumo_token(token)))
        db.commit()
    r = JSONResponse({'ok': True})
    r.delete_cookie(COOKIE, path='/')
    return r


@router.post('/auth/senha')
def mudar_senha(payload: SenhaIn, request: Request):
    identidade = autenticar(request)
    with SessionLocal() as db:
        u = db.get(Conta, identidade['id'])
        if not conferir(payload.atual, u.senha_hash):
            raise HTTPException(400, 'Senha atual incorreta.')
        if conferir(payload.nova, u.senha_hash):
            raise HTTPException(400, 'Escolha uma senha diferente.')
        u.senha_hash, u.trocar_senha = hash_senha(payload.nova), False
        db.execute(delete(Sessao).where(Sessao.conta_id == u.id))
        token = criar_sessao(db, u.id)
        registrar(db, identidade, 'troca_senha', u.id)
        db.commit()
    return cookie(JSONResponse({'ok': True}), request, token)


def admin(request):
    u = autenticar(request)
    if u['papel'] != 'admin':
        raise HTTPException(403, 'Somente administrador.')
    return u


@router.get('/auth/usuarios')
def usuarios(request: Request):
    admin(request)
    with SessionLocal() as db:
        return [publico(u) for u in db.scalars(select(Conta).order_by(Conta.login))]


@router.post('/auth/usuarios', status_code=201)
def criar_usuario(payload: ContaIn, request: Request):
    ator = admin(request)
    nome_login = payload.login.strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,40}', nome_login) or not payload.nome.strip() or payload.papel not in ('admin', 'usuario'):
        raise HTTPException(422, 'Confira login, nome e perfil.')
    with SessionLocal() as db:
        if db.scalar(select(Conta.id).where(Conta.login == nome_login)):
            raise HTTPException(409, 'Login ja cadastrado.')
        u = Conta(login=nome_login, nome=payload.nome.strip(), senha_hash=hash_senha(payload.senha), papel=payload.papel, ativo=True, trocar_senha=True)
        db.add(u)
        db.flush()
        registrar(db, ator, 'criar_usuario', u.id)
        dados = publico(u)
        db.commit()
        return dados


@router.patch('/auth/usuarios/{conta_id}')
def editar_usuario(conta_id: int, payload: ContaUpdate, request: Request):
    ator = admin(request)
    dados = payload.model_dump(exclude_unset=True)
    if any(v is None for v in dados.values()) or ('papel' in dados and dados['papel'] not in ('admin', 'usuario')):
        raise HTTPException(422, 'Perfil ou estado invalido.')
    if conta_id == ator['id'] and (dados.get('ativo') is False or dados.get('papel', 'admin') != 'admin' or 'senha' in dados):
        raise HTTPException(400, 'Use Alterar senha para sua conta. Nao e permitido desativar ou rebaixar a propria conta.')
    with SessionLocal() as db:
        u = db.get(Conta, conta_id)
        if not u:
            raise HTTPException(404, 'Usuario nao encontrado.')
        for k in ('ativo', 'papel'):
            if k in dados:
                setattr(u, k, dados[k])
        if 'senha' in dados:
            u.senha_hash, u.trocar_senha = hash_senha(dados['senha']), True
        db.execute(delete(Sessao).where(Sessao.conta_id == u.id))
        registrar(db, ator, 'editar_usuario', u.id)
        saida = publico(u)
        db.commit()
        return saida


@router.get('/auth/catalogo')
def catalogo(request: Request):
    autenticar(request)
    with SessionLocal() as db:
        produtos = db.scalars(select(Produto).where(Produto.ativo.is_(True))).all()
        nomes = {p.nome.strip().upper() for p in produtos}
        planos = db.scalars(select(Plano).where(Plano.ativo.is_(True))).all()
        return {'produtos': [{'nome': p.nome, 'dias': p.dias, 'duracao_fixa': p.duracao_fixa} for p in produtos],
                'planos': [{'id': p.id, 'nome': p.nome, 'produto': p.produto, 'valor': p.valor, 'dias': p.dias} for p in planos if (p.produto or '').strip().upper() in nomes]}


@router.get('/login', include_in_schema=False)
@router.get('/senha', include_in_schema=False)
@router.get('/usuarios', include_in_schema=False)
@router.get('/clientes', include_in_schema=False)
def pagina():
    return FileResponse(BASE_DIR / 'web' / 'acesso.html')


def sem_custos(obj):
    if isinstance(obj, list):
        return [sem_custos(v) for v in obj]
    if isinstance(obj, dict):
        return {k: sem_custos(v) for k, v in obj.items() if k not in {'custo', 'lucro', 'custo_credito', 'valor_custo', 'dados_extras'}}
    return obj


class ControleAcesso(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path.rstrip('/') or '/'
        metodo = request.method
        if metodo not in ('GET', 'HEAD', 'OPTIONS'):
            origem = request.headers.get('origin')
            if origem:
                o = urlsplit(origem)
                if o.scheme != request.url.scheme or o.netloc != request.headers.get('host'):
                    return JSONResponse({'detail': 'Origem invalida.'}, status_code=403)
            elif request.headers.get('x-painel') != '1':
                return JSONResponse({'detail': 'Cabecalho de protecao ausente.'}, status_code=403)
        publicas = (metodo == 'GET' and path in ('/login', '/health')) or (metodo == 'POST' and path == '/auth/login')
        u = identificar(request)
        request.state.identidade = u
        if not publicas:
            if not u:
                if metodo == 'GET' and (path in ('/', '/painel', '/clientes', '/usuarios', '/senha') or path.startswith('/painel/')):
                    return RedirectResponse('/login', status_code=303)
                return JSONResponse({'detail': 'Entre com login e senha.'}, status_code=401)
            if u['trocar_senha'] and path not in ('/senha', '/auth/senha', '/auth/me', '/auth/logout'):
                if metodo == 'GET' and (path == '/' or path == '/painel' or path.startswith('/painel/')):
                    return RedirectResponse('/senha', status_code=303)
                return JSONResponse({'detail': 'Troque a senha temporaria primeiro.'}, status_code=403)
            if u['papel'] == 'usuario' and path in ('/', '/painel'):
                return RedirectResponse('/clientes', status_code=303)
            if not permitido(u['papel'], metodo, path):
                return JSONResponse({'detail': 'Acesso nao permitido para este perfil.'}, status_code=403)
        resposta = await call_next(request)
        if u and path == '/painel' and metodo == 'GET' and resposta.status_code == 200:
            corpo = b''.join([c async for c in resposta.body_iterator]).decode('utf-8')
            inicio = "<script>localStorage.setItem('assinaturas.apiKey','sessao');</script>"
            fim = "<script>document.querySelector('.acoes')?.insertAdjacentHTML('afterbegin','<a class=\"botao\" href=\"/usuarios\">Usuários</a><a class=\"botao\" href=\"/senha\">Alterar senha</a>');document.addEventListener('click',async e=>{if(e.target.closest('#btnSair')){e.preventDefault();e.stopImmediatePropagation();await fetch('/auth/logout',{method:'POST',headers:{'X-Painel':'1'}});localStorage.removeItem('assinaturas.apiKey');location.href='/login'}},true);</script>"
            corpo = corpo.replace('<script>', inicio + '<script>', 1).replace('</body>', fim + '</body>')
            resposta = HTMLResponse(corpo, headers={k:v for k,v in resposta.headers.items() if k.lower() not in ('content-length', 'content-type')})
        elif u and u['papel'] == 'usuario' and path.startswith('/assinaturas') and resposta.status_code < 300 and 'application/json' in resposta.headers.get('content-type', ''):
            corpo = b''.join([c async for c in resposta.body_iterator])
            resposta = JSONResponse(sem_custos(json.loads(corpo)), status_code=resposta.status_code)
        if u and metodo in ('POST', 'PATCH', 'DELETE') and path.startswith('/assinaturas') and resposta.status_code < 300:
            with SessionLocal() as db:
                registrar(db, u, 'operacao_cliente', None)
                db.add(Evento(entidade='requisicao', acao=metodo.lower(), depois={'caminho': path, 'status': resposta.status_code}, origem='usuario:' + str(u['id'])))
                db.commit()
        resposta.headers['Cache-Control'] = 'no-store'
        resposta.headers['X-Content-Type-Options'] = 'nosniff'
        resposta.headers['X-Frame-Options'] = 'DENY'
        return resposta


HASH_FALSO = hash_senha(secrets.token_urlsafe(24))


def inicializar_contas():
    Base.metadata.create_all(engine, tables=[Conta.__table__, Sessao.__table__, Tentativa.__table__])
    with SessionLocal() as db:
        if not db.scalar(select(func.count(Conta.id))):
            db.add(Conta(login='admin', nome='Administrador', senha_hash=hash_senha('admin'), papel='admin', ativo=True, trocar_senha=True))
            registrar(db, None, 'admin_inicial')
            db.commit()
            return True
    return False


def instalar_login(app):
    app.include_router(router)
    app.add_middleware(ControleAcesso)
