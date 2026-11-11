"""Pare o painel e execute python habilitar_exclusao_produtos.py. Nao altera registros."""
import shutil
from datetime import datetime
from pathlib import Path


def trocar(texto, antigo, novo):
    if antigo in texto:
        if texto.count(antigo) != 1:
            raise RuntimeError('Trecho duplicado; nenhum arquivo alterado.')
        return texto.replace(antigo, novo, 1)
    if novo in texto:
        return texto
    raise RuntimeError('Versao inesperada. Nenhum arquivo alterado: ' + antigo[:90])


def main():
    raiz = Path(__file__).resolve().parent
    arquivos = {}
    p = raiz / 'web/gestao.html'
    t = p.read_text(encoding='utf-8')
    antigo = "if(ehPlano){const ex=document.createElement('button');ex.textContent='Excluir';ex.className='perigo';ex.onclick=()=>excluir(p);td.appendChild(ex)}"
    novo = "{const ex=document.createElement('button');ex.textContent='Excluir';ex.className='perigo';ex.onclick=()=>excluir(p);td.appendChild(ex)}"
    t = trocar(t, antigo, novo)
    t = t.replace("'Excluir o plano '+p.nome+'? Se houver clientes vinculados, a exclusão será bloqueada.'", "'Excluir '+tipo+' '+p.nome+' permanentemente? Se houver vínculos com clientes ou planos, a exclusão será bloqueada.'")
    t = t.replace("'Plano excluído.'", "'Item excluído.'")
    t = t.replace("'Este plano tem clientes vinculados. Arquivar sem alterar esses clientes?'", "'Este item tem vínculos com clientes ou planos. Arquivar sem alterar esses vínculos e históricos?'")
    t = t.replace("'Plano arquivado. Clientes preservados.'", "'Item arquivado. Clientes, planos e lançamentos preservados.'")
    arquivos[p] = t
    p = raiz / 'app/routers/produtos.py'
    t = p.read_text(encoding='utf-8')
    t = trocar(t, 'from ..models import Assinatura, Lancamento, Produto\n', 'from ..models import Assinatura, Lancamento, Plano, Produto\n')
    antigo = '    config = db.get(ConfigCredito, produto.id)\n    if config:\n        db.delete(config)\n'
    novo = '''    # exclusao_produto_com_vinculos_v1
    nome = produto.nome.strip().upper()
    clientes = db.scalar(select(func.count(Assinatura.id)).where(
        func.upper(func.trim(Assinatura.produto)) == nome
    )) or 0
    planos = db.scalar(select(func.count(Plano.id)).where(
        func.upper(func.trim(Plano.produto)) == nome
    )) or 0
    if clientes or planos:
        raise HTTPException(409, f"Produto vinculado a {clientes} cliente(s) e {planos} plano(s). Arquive para preservar os vinculos e custos.")
    config = db.get(ConfigCredito, produto.id)
    if config:
        db.delete(config)
        db.flush()
'''
    if '# exclusao_produto_com_vinculos_v1' not in t:
        t = trocar(t, antigo, novo)
    compile(t, str(p), 'exec')
    arquivos[p] = t
    backup = raiz / 'backups' / datetime.now().strftime('exclusao_produtos_%Y%m%d_%H%M%S_%f')
    for p in arquivos:
        b = backup / p.relative_to(raiz)
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
    try:
        for p, t in arquivos.items():
            p.write_text(t, encoding='utf-8')
    except Exception:
        for p in arquivos:
            shutil.copy2(backup / p.relative_to(raiz), p)
        raise
    print('Botao Excluir habilitado em Produtos, com confirmacao e protecao de vinculos.')
    print('Nenhum produto, cliente ou lancamento foi excluido pelo instalador.')
    print('Backup dos arquivos:', backup)
    print('Reinicie o painel e pressione Ctrl+F5. Nao execute a limpeza novamente.')

if __name__ == '__main__':
    main()
