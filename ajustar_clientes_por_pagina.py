"""Pare o painel: python ajustar_clientes_por_pagina.py. Nao acessa o banco."""
import re
import shutil
from datetime import datetime
from pathlib import Path


def aplicar(caminho, texto):
    original = texto
    # Front-end: define 10 como valor inicial do seletor de itens por pagina.
    for antigo, novo in [
        (r'(?i)(clientes[_ -]?por[_ -]?pagina|itens[_ -]?por[_ -]?pagina|per[_ -]?page|page[_ -]?size)\s*[=:]\s*(\d+)', r'\1 = 10'),
        (r'(?i)(data-(?:clientes-|itens-)?per-page|data-page-size)\s*=\s*"\d+"', r'\1="10"'),
        (r'(?i)(<select[^>]*id="(?:clientesPorPagina|itensPorPagina|perPage|pageSize)"[^>]*>)', r'\1'),
        (r'(?i)(<option[^>]*value=")(\d+)("[^>]*>\s*\d+\s*(?:clientes|itens|por página|por pagina)\s*</option>)', r'\g<1>10\g<3>'),
    ]:
        texto = re.sub(antigo, novo, texto)
    # Backend: limita a listagem de clientes a 10 quando nenhum limite for informado.
    for antigo, novo in [
        (r'(?i)(limit\s*[=:]\s*)(\d+)(?=[^a-z_])', r'\g<1>10'),
        (r'(?i)(per_page\s*[=:]\s*)(\d+)(?=[^a-z_])', r'\g<1>10'),
        (r'(?i)(page_size\s*[=:]\s*)(\d+)(?=[^a-z_])', r'\g<1>10'),
    ]:
        texto = re.sub(antigo, novo, texto)
    return texto if texto != original else None


def main():
    raiz = Path(__file__).resolve().parent
    alvos = []
    for pasta in ['web', 'app']:
        if (raiz / pasta).exists():
            alvos.extend((raiz / pasta).rglob('*'))
    alterados = []
    for p in alvos:
        if not p.is_file() or p.suffix.lower() not in {'.html', '.js', '.py'}:
            continue
        try:
            t = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        t2 = aplicar(p, t)
        if t2:
            alterados.append((p, t, t2))
    if not alterados:
        print('Nenhum controle de paginacao compativel foi encontrado. Nenhum arquivo alterado.')
        return
    backup = raiz / 'backups' / datetime.now().strftime('clientes_10_por_pagina_%Y%m%d_%H%M%S_%f')
    for p, _, _ in alterados:
        b = backup / p.relative_to(raiz)
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
    try:
        for p, _, t2 in alterados:
            p.write_text(t2, encoding='utf-8')
    except Exception:
        for p, _, _ in alterados:
            shutil.copy2(backup / p.relative_to(raiz), p)
        raise
    print('Clientes por pagina definidos como 10 por padrao no painel do cliente e do administrador.')
    print('O seletor continua disponivel para escolher outro valor.')
    print('Nenhum cadastro, valor, senha ou permissao foi alterado. Backup:', backup)
    print('Reinicie o painel e use Ctrl+F5. Nao execute a limpeza de novembro.')

if __name__ == '__main__':
    main()
