from .models import Evento
from .utils import serializar


def registrar(db, entidade: str, entidade_id: int | None, acao: str,
              antes: dict | None = None, depois: dict | None = None,
              origem: str = "api") -> None:
    db.add(
        Evento(
            entidade=entidade,
            entidade_id=entidade_id,
            acao=acao,
            antes={k: serializar(v) for k, v in (antes or {}).items()} or None,
            depois={k: serializar(v) for k, v in (depois or {}).items()} or None,
            origem=origem,
        )
    )
