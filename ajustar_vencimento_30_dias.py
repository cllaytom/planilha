"""Pare o painel: python ajustar_vencimento_30_dias.py. Nao acessa o banco."""
import shutil
from datetime import datetime
from pathlib import Path


def trocar(texto, antigo, novo):
    if novo in texto:
        return texto
    if texto.count(antigo) != 1:
        raise RuntimeError('Versao inesperada; nenhum arquivo alterado: ' + antigo[:100])
    return texto.replace(antigo, novo, 1)


def main():
    raiz = Path(__file__).resolve().parent
    arquivos = {}
    p = raiz / 'app/routers/assinaturas.py'
    t = p.read_text(encoding='utf-8')
    antigo = '''    if dados.get("vencimento") is None:
        produto_nome = dados.get("produto") or (plano.produto if plano else None)
        dias = _dias_do_produto(db, produto_nome, None, plano.dias if plano else None)
        dados["vencimento"] = date.today() + timedelta(days=dias)
'''
    novo = '''    if dados.get("vencimento") is None:
        # padrao_novo_cliente_30_dias_v1; data explicita continua respeitada.
        dados["vencimento"] = date.today() + timedelta(days=30)
'''
    t = trocar(t, antigo, novo)
    compile(t, str(p), 'exec')
    arquivos[p] = t
    p = raiz / 'web/acessos.js'
    t = p.read_text(encoding='utf-8')
    t = trocar(t, 'if(!editando)cliente=null;', 'if(!editando){cliente=null;vencimento(30)}')
    t = trocar(t, 'if(p&&!cliente)vencimento(p.dias);', '/* Mantem a data escolhida ao trocar produto. */')
    t = trocar(t, 'if(!cliente)vencimento(produto?.duracao_fixa?produto.dias:p.dias)', '/* Mantem a data escolhida ao trocar plano. */')
    arquivos[p] = t
    p = raiz / 'web/acesso.html'
    t = p.read_text(encoding='utf-8')
    if 'function dataPadrao30Dias()' not in t:
        marcador = "async function abrir(p=null,m=contas?'conta':'cliente'){"
        helper = "function dataPadrao30Dias(){const d=new Date();d.setDate(d.getDate()+30);return[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')}\n"
        t = trocar(t, marcador, helper + marcador)
    t = trocar(t, "$('vencimento').value=p?.vencimento||'';", "$('vencimento').value=p?(p.vencimento||''):dataPadrao30Dias();")
    arquivos[p] = t
    backup = raiz / 'backups' / datetime.now().strftime('vencimento_30_dias_%Y%m%d_%H%M%S_%f')
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
    print('Novo cliente: vencimento padrao de hoje + 30 dias, com edicao manual.')
    print('Trocar produto/plano nao sobrescreve a data. Clientes antigos e renovacoes preservados.')
    print('Nenhum registro foi alterado. Backup:', backup)
    print('Reinicie o painel e use Ctrl+F5. Nao execute a limpeza de novembro.')

if __name__ == '__main__':
    main()
