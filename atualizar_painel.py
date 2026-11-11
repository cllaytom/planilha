"""Execute com o servidor parado: python atualizar_painel.py --aplicar."""
import argparse
import json
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, select, update
from app.database import SessionLocal, engine
from app.models import Evento, Lancamento, Plano

ROOT = Path(__file__).resolve().parent
MARCA = 'ajuste_acessos_novembro_2026_v1'


def trocar(texto, antigo, novo):
    if novo in texto:
        return texto
    if texto.count(antigo) != 1:
        raise RuntimeError('Arquivo diferente do esperado; nada foi limpo. Trecho: ' + antigo[:100])
    return texto.replace(antigo, novo, 1)


def preparar():
    arquivos = {}
    p = ROOT / 'app/main.py'
    t = p.read_text(encoding='utf-8')
    t = trocar(t, '    produtos.preparar_dados()', '    # Cadastro e financeiro nao sao mais recriados automaticamente.')
    t = trocar(t, '    return HTMLResponse(html.replace(', '    html = html.replace("</body>", \'<script src="/acessos.js"></script></body>\')\n    return HTMLResponse(html.replace(')
    if '@app.get("/acessos.js"' not in t:
        t += '\n@app.get("/acessos.js", include_in_schema=False)\ndef script_acessos():\n    return FileResponse(BASE_DIR / "web" / "acessos.js", media_type="application/javascript")\n'
    arquivos[p] = t
    p = ROOT / 'app/database.py'
    t = p.read_text(encoding='utf-8')
    t = trocar(t, '        if not custo:\n            continue\n', '        if not custo:\n            continue\n        quantidade = ass.conexoes or 1\n        if quantidade < 1:\n            raise HTTPException(422, "Quantidade de acessos deve ser positiva.")\n        custo = custo * quantidade\n')
    t = trocar(t, 'Custo de 1 credito de {produto.nome}', 'Custo de {quantidade} acesso(s) de {produto.nome}')
    arquivos[p] = t
    p = ROOT / 'app/schemas.py'
    t = p.read_text(encoding='utf-8')
    t = t.replace('    conexoes: int = 1', '    conexoes: int = Field(default=1, ge=1)')
    t = t.replace('    conexoes: int | None = None', '    conexoes: int | None = Field(default=None, ge=1)')
    arquivos[p] = t
    for p, t in arquivos.items():
        compile(t, str(p), 'exec')
    return arquivos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true')
    args = parser.parse_args()
    if not args.aplicar:
        parser.error('Pare o servidor e use --aplicar. A limpeza inclui todo novembro de 2026.')
    if engine.dialect.name != 'sqlite' or not engine.url.database or engine.url.database == ':memory:':
        raise RuntimeError('Atualizacao automatica permitida somente em banco SQLite de arquivo.')
    arquivos = preparar()
    destino = ROOT / 'backups' / datetime.now().strftime('ajuste_%Y%m%d_%H%M%S_%f')
    destino.mkdir(parents=True)
    origem = sqlite3.connect(str(engine.url.database))
    copia = sqlite3.connect(str(destino / 'banco.sqlite3'))
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    for p in arquivos:
        backup = destino / p.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, backup)
    gravados = []
    try:
        for p, texto in arquivos.items():
            p.write_text(texto, encoding='utf-8')
            gravados.append(p)
        with SessionLocal() as db:
            with db.begin():
                ja = db.scalar(select(Evento.id).where(Evento.acao == MARCA).limit(1))
                if ja:
                    resultado = {'limpeza': 'ja executada; novos lancamentos preservados'}
                else:
                    cond = (Lancamento.data >= date(2026, 11, 1), Lancamento.data < date(2026, 12, 1))
                    linhas = db.scalars(select(Lancamento).where(*cond)).all()
                    exportados = [{c.name: getattr(l, c.name) for c in Lancamento.__table__.columns} for l in linhas]
                    (destino / 'lancamentos_novembro.json').write_text(json.dumps(exportados, default=str, ensure_ascii=False, indent=2), encoding='utf-8')
                    quantidade = len(linhas)
                    db.execute(delete(Lancamento).where(*cond))
                    planos = db.execute(update(Plano).values(ativo=False)).rowcount
                    resultado = {'lancamentos_removidos': quantidade, 'planos_desativados': planos}
                    db.add(Evento(entidade='manutencao', acao=MARCA, depois=resultado, origem='atualizador_manual'))
        print(json.dumps(resultado, ensure_ascii=False))
        print('Backup salvo em:', destino)
        print('Concluido. Inicie novamente o painel e atualize o navegador com Ctrl+F5.')
    except Exception:
        for p in gravados:
            shutil.copy2(destino / p.relative_to(ROOT), p)
        raise


if __name__ == '__main__':
    main()
