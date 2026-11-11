"""Importa a planilha original para o banco da API.

Uso:
    python scripts/importar_planilha.py "D:\\caminho\\planilha.xlsb"
    python scripts/importar_planilha.py "D:\\caminho\\planilha.xlsb" --recalcular-status
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.importer import importar_planilha  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa planilha de assinaturas para o SQLite.")
    parser.add_argument("arquivo", help="Caminho do arquivo .xlsb/.xlsx")
    parser.add_argument("--aba", default="BASE DE DADOS", help="Nome da aba com os dados")
    parser.add_argument("--aba-planos", default="PLANOS E VALORES", help="Aba do catalogo de planos")
    parser.add_argument(
        "--recalcular-status",
        action="store_true",
        help="Define ATIVO/INATIVO com base na data de vencimento (em vez de copiar a coluna Status).",
    )
    args = parser.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.exists():
        print(f"Arquivo nao encontrado: {caminho}")
        return 1

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        resultado = importar_planilha(
            caminho,
            db,
            aba=args.aba,
            aba_planos=args.aba_planos,
            recalcular_status=args.recalcular_status,
        )

    print("Importacao concluida:")
    for chave, valor in resultado.items():
        if chave == "erros":
            print(f"  erros: {len(valor)}")
            for erro in valor[:10]:
                print(f"    - {erro}")
        else:
            print(f"  {chave}: {valor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
