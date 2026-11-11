"""Com o painel parado: python instalar_dashboard_usuario.py. Nao acessa o banco."""
import ast
import shutil
from datetime import datetime
from pathlib import Path


def main():
    raiz = Path(__file__).resolve().parent
    for relativo in ('app/dashboard_usuario.py', 'web/dashboard_usuario.js'):
        if not (raiz / relativo).is_file():
            raise RuntimeError('Execute git pull. Arquivo ausente: ' + relativo)
    p = raiz / 'app/main.py'
    t = p.read_text(encoding='utf-8')
    if '# login_perfis_v1' not in t:
        raise RuntimeError('Instale o login antes com python instalar_login.py. Nenhum arquivo alterado.')
    if '# dashboard_usuario_v1' not in t:
        t += '\n# dashboard_usuario_v1\nfrom .dashboard_usuario import router as dashboard_usuario_router\napp.include_router(dashboard_usuario_router)\n'
    arquivos = {p: t}
    p = raiz / 'app/acesso_regras.py'
    t = p.read_text(encoding='utf-8')
    if "'/auth/vencimentos'" not in t:
        antigo = "('/clientes', '/senha', '/auth/me', '/auth/catalogo')"
        if t.count(antigo) != 1:
            raise RuntimeError('Politica de acesso inesperada. Nenhum arquivo alterado.')
        t = t.replace(antigo, "('/clientes', '/senha', '/auth/me', '/auth/catalogo', '/auth/vencimentos')", 1)
    arquivos[p] = t
    p = raiz / 'web/acesso.html'
    t = p.read_text(encoding='utf-8')
    if '<!-- dashboard_usuario_v1 -->' not in t:
        if t.count('</html>') != 1:
            raise RuntimeError('Pagina inesperada. Nenhum arquivo alterado.')
        js = (raiz / 'web/dashboard_usuario.js').read_text(encoding='utf-8')
        if '</script' in js.lower():
            raise RuntimeError('Conteudo de script inesperado.')
        t = t.replace('</html>', '<!-- dashboard_usuario_v1 --><script>' + js + '</script></html>', 1)
    arquivos[p] = t
    for p,t in arquivos.items():
        if p.suffix == '.py':
            ast.parse(t)
    backup = raiz / 'backups' / datetime.now().strftime('dashboard_usuario_%Y%m%d_%H%M%S_%f')
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
    print('Dashboard de vencimentos instalado para perfil usuario, sem valores financeiros.')
    print('Nenhum registro ou senha foi alterado. Backup:', backup)
    print('Reinicie e use Ctrl+F5. Nao execute a limpeza de novembro.')

if __name__ == '__main__':
    main()
