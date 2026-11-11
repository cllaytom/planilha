"""Exporta o banco atual para um .xlsx.

Uso:
    python scripts/exportar_planilha.py [saida.xlsx]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.exporter import gerar_xlsx  # noqa: E402


def main() -> int:
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("assinaturas.xlsx")
    with SessionLocal() as db:
        buffer = gerar_xlsx(db)
    saida.write_bytes(buffer.getvalue())
    print(f"Arquivo gerado: {saida.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
