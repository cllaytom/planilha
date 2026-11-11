from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db
from ..exporter import gerar_xlsx
from ..importer import importar_planilha
from ..schemas import ImportacaoResultado
from ..security import verificar_api_key

router = APIRouter(
    prefix="/admin",
    tags=["administracao"],
    dependencies=[Depends(verificar_api_key)],
)

EXTENSOES = {".xlsb", ".xlsx", ".xlsm"}


@router.post("/importacao/excel", response_model=ImportacaoResultado,
             summary="Importar planilha (.xlsb/.xlsx) para o banco")
def importar_excel(
    arquivo: UploadFile = File(...),
    aba: str = "BASE DE DADOS",
    recalcular_status: bool = False,
    db: Session = Depends(get_db),
):
    sufixo = Path(arquivo.filename or "").suffix.lower()
    if sufixo not in EXTENSOES:
        raise HTTPException(status_code=422, detail=f"Formato nao suportado: {sufixo or 'desconhecido'}.")

    pasta = DATA_DIR / "importacoes"
    pasta.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo, dir=pasta) as tmp:
        tmp.write(arquivo.file.read())
        caminho = Path(tmp.name)

    try:
        return importar_planilha(caminho, db, aba=aba, recalcular_status=recalcular_status)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Falha ao importar: {exc}") from exc
    finally:
        caminho.unlink(missing_ok=True)


@router.get("/exportacao/excel", summary="Exportar a base atual como .xlsx")
def exportar_excel(db: Session = Depends(get_db)):
    buffer = gerar_xlsx(db)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="assinaturas.xlsx"'},
    )
