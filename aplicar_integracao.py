"""Pare o painel e execute python aplicar_integracao.py. Nao conecta ao banco."""
import ast
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def retorno_da_funcao(texto, nome, expressao):
    arvore = ast.parse(texto)
    funcoes = [n for n in arvore.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nome]
    if len(funcoes) != 1:
        raise ValueError('Funcao inesperada: ' + nome)
    retornos = [n for n in funcoes[0].body if isinstance(n, ast.Return)]
    if len(retornos) != 1:
        raise ValueError('Retorno inesperado: ' + nome)
    n = retornos[0]
    linhas = texto.splitlines(keepends=True)
    linhas[n.lineno-1:n.end_lineno] = [' ' * n.col_offset + 'return ' + expressao + '\n']
    saida = ''.join(linhas)
    ast.parse(saida)
    return saida


def trocar(texto, antigo, novo):
    if texto.count(antigo) == 1:
        return texto.replace(antigo, novo, 1)
    if novo in texto:
        return texto
    raise ValueError('Trecho inesperado; nenhum dado foi alterado: ' + antigo[:100])


def preparar(raiz):
    arquivos = {}
    p = raiz / 'app/main.py'
    t = p.read_text(encoding='utf-8')
    expressao = 'FileResponse(BASE_DIR / "web" / "gestao.html")'
    for nome in ('cadastro_produtos', 'tela_planos'):
        t = retorno_da_funcao(t, nome, expressao)
    t = t.replace('    produtos.preparar_dados()', '    # Sem recriacao automatica de produtos ou pagamentos.')
    if '<script src="/acessos.js"></script>' not in t:
        t = trocar(t, '    return HTMLResponse(html.replace(', '    html = html.replace("</body>", \'<script src="/acessos.js"></script></body>\')\n    return HTMLResponse(html.replace(')
    if '@app.get("/acessos.js"' not in t:
        t += '\n@app.get("/acessos.js", include_in_schema=False)\ndef script_acessos():\n    return FileResponse(BASE_DIR / "web" / "acessos.js", media_type="application/javascript")\n'
    arquivos[p] = t
    p = raiz / 'app/database.py'
    t = p.read_text(encoding='utf-8')
    if 'custo = custo * quantidade' not in t:
        t = trocar(t, '        if not custo:\n            continue\n', '        if not custo:\n            continue\n        quantidade = ass.conexoes if ass.conexoes is not None else 1\n        if quantidade < 1:\n            raise HTTPException(422, "Quantidade de acessos deve ser positiva.")\n        custo = custo * quantidade\n')
        t = trocar(t, 'Custo de 1 credito de {produto.nome}', 'Custo de {quantidade} acesso(s) de {produto.nome}')
    t = t.replace('quantidade = ass.conexoes or 1', 'quantidade = ass.conexoes if ass.conexoes is not None else 1')
    arquivos[p] = t
    p = raiz / 'app/routers/assinaturas.py'
    t = p.read_text(encoding='utf-8')
    antigo = '    plano = _resolver_plano(db, dados.get("plano_id"), dados.get("plano_nome"))\n'
    novo = antigo + '    if (dados.get("plano_id") or dados.get("plano_nome")) and (plano is None or not plano.ativo):\n        raise HTTPException(422, "Selecione um plano ativo ou cadastre diretamente pelo produto.")\n    if dados.get("conexoes", 1) < 1:\n        raise HTTPException(422, "Quantidade de acessos deve ser positiva.")\n'
    if novo not in t:
        t = trocar(t, antigo, novo)
    t = trocar(t, '            plano = _resolver_plano(db, ass.plano_id, ass.plano_nome)\n', '            plano = _resolver_plano(db, dados.get("plano_id"), dados.get("plano_nome"))\n            if plano is None:\n                raise HTTPException(422, "Plano informado nao encontrado.")\n')
    arquivos[p] = t
    p = raiz / 'web/acessos.js'
    t = p.read_text(encoding='utf-8')
    t = trocar(t, " $('novoPlano').addEventListener('change',()=>{", " $('novoPlano').addEventListener('change',evento=>{evento.stopImmediatePropagation();")
    t = trocar(t, 'if(!cliente)vencimento(produto?.duracao_fixa?produto.dias:p.dias)}});', 'if(!cliente)vencimento(produto?.duracao_fixa?produto.dias:p.dias)}},true);')
    if 'function mesmoProduto(' not in t:
        t = trocar(t, ' function planosDoProduto(', " function mesmoProduto(a,b){return String(a||'').trim().toLocaleUpperCase('pt-BR')===String(b||'').trim().toLocaleUpperCase('pt-BR')}\n function planosDoProduto(")
    t = t.replace("p.produto===$('clienteProduto').value", "mesmoProduto(p.produto,$('clienteProduto').value)")
    t = t.replace('x.nome===p.produto', 'mesmoProduto(x.nome,p.produto)')
    t = t.replace('p.produto===produto.nome', 'mesmoProduto(p.produto,produto.nome)')
    arquivos[p] = t
    for p, conteudo in arquivos.items():
        if p.suffix == '.py':
            compile(conteudo, str(p), 'exec')
    return arquivos


def main():
    arquivos = preparar(ROOT)
    for requerido in ('web/gestao.html', 'app/regras_planos.py'):
        if not (ROOT / requerido).is_file():
            raise RuntimeError('Atualizacao incompleta. Execute git pull antes.')
    backup = ROOT / 'backups' / datetime.now().strftime('planos_%Y%m%d_%H%M%S_%f')
    for p in arquivos:
        destino = backup / p.relative_to(ROOT)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, destino)
    try:
        for p, conteudo in arquivos.items():
            p.write_text(conteudo, encoding='utf-8')
    except Exception:
        for p in arquivos:
            shutil.copy2(backup / p.relative_to(ROOT), p)
        raise
    print('Correcao aplicada. Ambas as telas de gestao foram atualizadas.')
    print('Nenhum cliente ou lancamento foi alterado. Limpeza NAO executada.')
    print('Backup dos arquivos:', backup)
    print('Reinicie o painel e pressione Ctrl+F5 no navegador.')

if __name__ == '__main__':
    main()
