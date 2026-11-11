"""Com o painel parado, execute python ajustar_senha_minima.py. Nao acessa o banco."""
import shutil
from datetime import datetime
from pathlib import Path


def main():
    raiz = Path(__file__).resolve().parent
    backend = raiz / 'app/acesso_login.py'
    tela = raiz / 'web/acesso.html'
    t = backend.read_text(encoding='utf-8')
    h = tela.read_text(encoding='utf-8')
    if t.count('min_length=12') not in (0, 3):
        raise RuntimeError('Versao inesperada da autenticacao. Nenhum arquivo alterado.')
    if 'min_length=12' not in t and t.count('min_length=4') < 3:
        raise RuntimeError('Validacoes de senha nao localizadas. Nenhum arquivo alterado.')
    if 'minlength="12"' not in h and 'minlength="4"' not in h:
        raise RuntimeError('Validacao do formulario nao localizada. Nenhum arquivo alterado.')
    t = t.replace('min_length=12', 'min_length=4')
    h = h.replace('minlength="12"', 'minlength="4"').replace('12 caracteres', '4 caracteres')
    compile(t, str(backend), 'exec')
    backup = raiz / 'backups' / datetime.now().strftime('senha_minima_%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True)
    shutil.copy2(backend, backup / 'acesso_login.py')
    shutil.copy2(tela, backup / 'acesso.html')
    try:
        backend.write_text(t, encoding='utf-8')
        tela.write_text(h, encoding='utf-8')
    except Exception:
        shutil.copy2(backup / 'acesso_login.py', backend)
        shutil.copy2(backup / 'acesso.html', tela)
        raise
    print('Minimo alterado para 4 caracteres no servidor e no formulario.')
    print('Senhas existentes preservadas. Troca inicial continua obrigatoria.')
    print('Aviso: quatro caracteres oferecem protecao fraca; nao recomendado para exposicao na internet.')
    print('Backup:', backup)
    print('Reinicie o painel e pressione Ctrl+F5. Nenhuma limpeza foi executada.')

if __name__ == '__main__':
    main()
