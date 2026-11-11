"""Pare o painel e execute python ajustar_layout_usuario.py. Nao acessa o banco."""
import shutil
from datetime import datetime
from pathlib import Path


def main():
    raiz = Path(__file__).resolve().parent
    js = (raiz / 'web/layout_usuario.js').read_text(encoding='utf-8')
    p = raiz / 'app/dashboard_usuario.py'
    t = p.read_text(encoding='utf-8')
    if t.count('for i in range(6):') == 1:
        t = t.replace('for i in range(6):', 'for i in range(3):', 1)
    elif t.count('for i in range(3):') != 1:
        raise RuntimeError('Periodo do dashboard inesperado. Nenhum arquivo alterado.')
    compile(t, str(p), 'exec')
    arquivos = {p: t}
    p = raiz / 'web/acesso.html'
    t = p.read_text(encoding='utf-8')
    if '<!-- dashboard_usuario_v1 -->' not in t:
        raise RuntimeError('Instale o dashboard do usuario primeiro. Nenhum arquivo alterado.')
    if '<!-- layout_usuario_v1 -->' not in t:
        if t.count('</html>') != 1 or '</script' in js.lower():
            raise RuntimeError('Pagina ou script inesperado. Nenhum arquivo alterado.')
        t = t.replace('</html>', '<!-- layout_usuario_v1 --><script>' + js + '</script></html>', 1)
    arquivos[p] = t
    backup = raiz / 'backups' / datetime.now().strftime('layout_usuario_%Y%m%d_%H%M%S_%f')
    for p in arquivos:
        b = backup / p.relative_to(raiz)
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
    try:
        for p,t in arquivos.items():
            p.write_text(t, encoding='utf-8')
    except Exception:
        for p in arquivos:
            shutil.copy2(backup / p.relative_to(raiz), p)
        raise
    print('Layout ajustado: Novo cliente junto a base e grafico com tres meses.')
    print('Nenhum registro, valor, senha ou permissao foi alterado. Backup:', backup)
    print('Reinicie e use Ctrl+F5. Nao execute a limpeza de novembro.')

if __name__ == '__main__':
    main()
