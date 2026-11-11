"""Pare o painel: python ajustar_limite_10_clientes.py. Nao acessa o banco."""
import shutil
from datetime import datetime
from pathlib import Path


def main():
    raiz = Path(__file__).resolve().parent
    p = raiz / 'app/routers/assinaturas.py'
    t = p.read_text(encoding='utf-8')
    antigo = 'limite: int = Query(default=50, ge=1, le=500),'
    novo = 'limite: int = Query(default=10, ge=1, le=500),'
    if novo in t:
        print('O limite padrao ja esta em 10 clientes por pagina. Nenhum arquivo alterado.')
        return
    if t.count(antigo) != 1:
        raise RuntimeError('Linha do limite nao encontrada ou duplicada. Nenhum arquivo alterado.')
    t = t.replace(antigo, novo, 1)
    compile(t, str(p), 'exec')
    backup = raiz / 'backups' / datetime.now().strftime('limite_10_clientes_%Y%m%d_%H%M%S_%f')
    destino = backup / p.relative_to(raiz)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, destino)
    try:
        p.write_text(t, encoding='utf-8')
    except Exception:
        shutil.copy2(destino, p)
        raise
    print('Limite padrao da listagem de clientes alterado de 50 para 10.')
    print('Vale para o painel do cliente e do administrador.')
    print('O seletor continua disponivel para escolher outro valor.')
    print('Nenhum cadastro, valor, senha ou permissao foi alterado. Backup:', backup)
    print('Reinicie o painel e use Ctrl+F5. Nao execute a limpeza de novembro.')

if __name__ == '__main__':
    main()
