"""Pare o painel. Execute: python aplicar_integracao.py. Nao limpa dados."""
from datetime import datetime
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent

def substituir(t, antigo, novo):
    if novo in t:
        return t
    if t.count(antigo) != 1:
        raise RuntimeError('Versao de arquivo inesperada. Nenhuma limpeza foi feita: ' + antigo[:80])
    return t.replace(antigo, novo, 1)


def main():
    p = root / 'app/main.py'
    t = p.read_text(encoding='utf-8')
    t = substituir(t, 'return FileResponse(BASE_DIR / "web" / "produtos.html")', 'return FileResponse(BASE_DIR / "web" / "gestao.html")')
    t = substituir(t, 'return HTMLResponse(PLANOS_HTML)', 'return FileResponse(BASE_DIR / "web" / "gestao.html")')
    t = t.replace('    produtos.preparar_dados()', '    # Nao recriar produtos ou pagamentos automaticamente.')
    if '<script src="/acessos.js"></script>' not in t:
        t = substituir(t, '    return HTMLResponse(html.replace(', '    html = html.replace("</body>", \'<script src="/acessos.js"></script></body>\')\n    return HTMLResponse(html.replace(')
    if '@app.get("/acessos.js"' not in t:
        t += '\n@app.get("/acessos.js", include_in_schema=False)\ndef script_acessos():\n    return FileResponse(BASE_DIR / "web" / "acessos.js", media_type="application/javascript")\n'
    arquivos = {p: t}
    p = root / 'app/database.py'
    t = p.read_text(encoding='utf-8')
    if 'custo = custo * quantidade' not in t:
        t = substituir(t, '        if not custo:\n            continue\n', '        if not custo:\n            continue\n        quantidade = ass.conexoes or 1\n        if quantidade < 1:\n            raise HTTPException(422, "Quantidade de acessos deve ser positiva.")\n        custo = custo * quantidade\n')
        t = substituir(t, 'Custo de 1 credito de {produto.nome}', 'Custo de {quantidade} acesso(s) de {produto.nome}')
    arquivos[p] = t
    for p,t in arquivos.items():
        compile(t, str(p), 'exec')
    backup = root / 'backups' / datetime.now().strftime('interface_%Y%m%d_%H%M%S_%f')
    for p in arquivos:
        b = backup / p.relative_to(root)
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
    try:
        for p,t in arquivos.items():
            p.write_text(t, encoding='utf-8')
    except Exception:
        for p in arquivos:
            shutil.copy2(backup / p.relative_to(root), p)
        raise
    print('Integracao aplicada. Nenhum registro do banco foi alterado.')
    print('Backup dos arquivos:', backup)
    print('Inicie o painel e atualize com Ctrl+F5. NAO execute a limpeza novamente.')

if __name__ == '__main__':
    main()
