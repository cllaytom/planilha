"""Execute com o painel parado: python corrigir_valores.py. Nao altera dados."""
import ast
import shutil
from datetime import datetime
from pathlib import Path


def main():
    raiz = Path(__file__).resolve().parent
    if not (raiz / 'web/moeda.js').is_file():
        raise RuntimeError('Execute git pull antes. Arquivo moeda.js ausente.')
    p = raiz / 'app/main.py'
    texto = p.read_text(encoding='utf-8')
    if '# moeda_automatica_v2' in texto:
        print('Mascara ja instalada. Reinicie o painel e pressione Ctrl+F5.')
        return
    arvore = ast.parse(texto)
    funcoes = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'painel']
    if len(funcoes) != 1:
        raise RuntimeError('Funcao painel inesperada. Nenhum arquivo alterado.')
    retornos = [n for n in funcoes[0].body if isinstance(n, ast.Return)]
    if len(retornos) != 1:
        raise RuntimeError('Retorno do painel inesperado. Nenhum arquivo alterado.')
    linhas = texto.splitlines(keepends=True)
    indice = retornos[0].lineno - 1
    linhas[indice:indice] = ['    # moeda_automatica_v2\n', '    html = html.replace("</body>", "<script>" + (BASE_DIR / "web" / "moeda.js").read_text(encoding="utf-8") + "</script></body>")\n']
    novo = ''.join(linhas)
    compile(novo, str(p), 'exec')
    pasta = raiz / 'backups' / datetime.now().strftime('moeda_%Y%m%d_%H%M%S_%f')
    pasta.mkdir(parents=True)
    shutil.copy2(p, pasta / 'main.py')
    try:
        p.write_text(novo, encoding='utf-8')
    except Exception:
        shutil.copy2(pasta / 'main.py', p)
        raise
    print('Mascara automatica instalada. Nenhum dado do banco foi alterado.')
    print('Backup:', pasta)
    print('Reinicie e use Ctrl+F5. Digite 2000 para visualizar R$ 20,00.')

if __name__ == '__main__':
    main()
