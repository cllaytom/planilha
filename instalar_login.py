"""Pare o painel. Execute python instalar_login.py. Preserva o banco existente."""
import ast
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def main():
    raiz = Path(__file__).resolve().parent
    from app.database import engine
    if engine.dialect.name != 'sqlite' or not engine.url.database or not Path(engine.url.database).is_file():
        raise RuntimeError('Instalacao automatica exige o banco SQLite existente. Nenhum dado alterado.')
    for relativo in ('app/acesso_regras.py', 'app/acesso_login.py', 'web/acesso.html'):
        if not (raiz / relativo).is_file():
            raise RuntimeError('Atualizacao incompleta: ' + relativo)
    principal = raiz / 'app/main.py'
    seguranca = raiz / 'app/security.py'
    texto = principal.read_text(encoding='utf-8')
    texto = texto.replace('    produtos.preparar_dados()', '    # Sem recriacao automatica de dados.')
    if '# login_perfis_v1' not in texto:
        texto += '\n# login_perfis_v1\nfrom .acesso_login import instalar_login\ninstalar_login(app)\n'
    novo_security = 'from .acesso_login import verificar_api_key\n'
    ast.parse(texto)
    compile(texto, str(principal), 'exec')
    pasta = raiz / 'backups' / datetime.now().strftime('login_%Y%m%d_%H%M%S_%f')
    pasta.mkdir(parents=True)
    origem = sqlite3.connect(str(engine.url.database))
    destino = sqlite3.connect(str(pasta / 'banco.sqlite3'))
    try:
        origem.backup(destino)
    finally:
        origem.close()
        destino.close()
    shutil.copy2(principal, pasta / 'main.py')
    shutil.copy2(seguranca, pasta / 'security.py')
    from app.acesso_login import inicializar_contas
    criado = inicializar_contas()
    try:
        principal.write_text(texto, encoding='utf-8')
        seguranca.write_text(novo_security, encoding='utf-8')
    except Exception:
        shutil.copy2(pasta / 'main.py', principal)
        shutil.copy2(pasta / 'security.py', seguranca)
        raise
    print('Login instalado. Clientes, planos e lancamentos preservados.')
    print('Admin inicial criado: admin / admin. Troca obrigatoria no primeiro acesso.' if criado else 'Contas existentes preservadas; nenhuma senha foi restaurada.')
    print('Backup completo:', pasta)
    print('Inicie o painel e abra /login neste computador. Nao execute a limpeza de novembro.')

if __name__ == '__main__':
    main()
