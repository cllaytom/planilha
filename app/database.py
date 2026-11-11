import logging
from datetime import date

from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _ativar_chaves_estrangeiras(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


@event.listens_for(SessionLocal, "before_flush")
def _registrar_custo_de_credito(db, flush_context, instances):
    from .custos_creditos import custo_da_operacao
    from .models import Assinatura, Evento, Lancamento, Plano, Produto
    from .routers.creditos_config import ConfigCredito

    novos = list(db.new)
    for receita in novos:
        if not isinstance(receita, Lancamento) or not receita.assinatura_id:
            continue
        if receita.tipo not in ("pagamento", "renovacao"):
            continue
        ass = db.get(Assinatura, receita.assinatura_id)
        if ass is None:
            continue
        criacao = any(isinstance(e, Evento) and e.entidade == "assinatura"
                      and e.entidade_id == ass.id and e.acao == "criacao"
                      for e in novos)
        if receita.tipo == "pagamento":
            # Somente pagamento inicial da criacao atual. Nao cobra importados,
            # pagamentos avulsos nem a regularizacao automatica ao reiniciar.
            if not criacao or receita.descricao != "Pagamento inicial (automatico)":
                continue
            dias = (ass.vencimento - date.today()).days if ass.vencimento else None
        else:
            historico = inspect(ass).attrs.vencimento.history
            if not historico.has_changes() or not historico.added:
                continue
            anterior = historico.deleted[0] if historico.deleted else None
            base = max(anterior or date.today(), date.today())
            dias = (ass.vencimento - base).days if ass.vencimento else None

        plano = db.get(Plano, ass.plano_id) if ass.plano_id else None
        if plano is None and ass.plano_nome:
            plano = db.scalar(select(Plano).where(func.upper(Plano.nome) == ass.plano_nome.strip().upper()))
        nome_produto = ass.produto or (plano.produto if plano else None)
        if not nome_produto:
            raise HTTPException(422, "Selecione um plano vinculado a um produto antes de vender ou renovar. Nenhuma operacao foi salva.")
        produto = db.scalar(select(Produto).where(func.upper(Produto.nome) == nome_produto.strip().upper()))
        if produto is None:
            raise HTTPException(422, "Produto nao cadastrado. Confira o produto do plano em Produtos.")
        if produto.nome.strip().casefold() == "internet" and dias != 30:
            continue
        config = db.get(ConfigCredito, produto.id)
        if config is None:
            raise HTTPException(422, "Salve a configuracao de custo e consumo deste produto antes da venda ou renovacao.")
        if config.regra == 2 and dias is None:
            raise HTTPException(422, "Nao foi possivel identificar a duracao para calcular o custo.")
        try:
            custo = custo_da_operacao(produto.nome, config.controlar_estoque,
                                     config.regra, config.custo_credito, dias)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not custo:
            continue
        # Ambos os lancamentos fazem parte do mesmo flush/commit.
        # Atualizar a pagina ou reiniciar nao reprocessa receitas persistidas.
        db.add(Lancamento(
            assinatura_id=ass.id,
            tipo="despesa",
            data=receita.data or date.today(),
            valor=float(custo),
            plano_nome=receita.plano_nome or ass.plano_nome,
            descricao=f"Custo de 1 credito de {produto.nome}: {ass.nome}; {dias} dias; {receita.tipo}",
        ))
        db.add(Evento(entidade="assinatura", entidade_id=ass.id, acao="custo_credito",
                      depois={"produto_id": produto.id, "dias": dias, "custo": str(custo)},
                      origem="api"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
