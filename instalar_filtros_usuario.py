"""Pare o painel: python instalar_filtros_usuario.py. Nao acessa o banco."""
import shutil
from datetime import datetime
from pathlib import Path


def trocar(texto, antigo, novo):
    if novo in texto:
        return texto
    if texto.count(antigo) != 1:
        raise RuntimeError('Versao inesperada. Nenhum arquivo alterado: ' + antigo[:100])
    return texto.replace(antigo, novo, 1)


def main():
    raiz = Path(__file__).resolve().parent
    js = (raiz / 'web/filtros_usuario.js').read_text(encoding='utf-8')
    p = raiz / 'app/routers/assinaturas.py'
    t = p.read_text(encoding='utf-8')
    if '# filtro_dashboard_usuario_v1' not in t:
        marcador = '    ordenar_por: str = Query(default="nome", description="nome | vencimento | valor | id"),\n'
        t = trocar(t, marcador, '    filtro_dashboard: str | None = Query(default=None),\n' + marcador)
        marcador = '    stmt = select(Assinatura)\n'
        bloco = '''    # filtro_dashboard_usuario_v1
    if filtro_dashboard is not None:
        if filtro_dashboard not in {"todos", "atrasados", "hoje", "sete", "em_dia"}:
            raise HTTPException(422, "Filtro de vencimentos invalido.")
        stmt = stmt.where(Assinatura.status != "CANCELADO")
        if filtro_dashboard != "todos":
            stmt = stmt.where(Assinatura.status.notin_(["INATIVO", "SUSPENSO"]))
            if filtro_dashboard == "atrasados":
                stmt = stmt.where(Assinatura.vencimento < hoje)
            elif filtro_dashboard == "hoje":
                stmt = stmt.where(Assinatura.vencimento == hoje)
            elif filtro_dashboard == "sete":
                stmt = stmt.where(Assinatura.vencimento > hoje, Assinatura.vencimento <= hoje + timedelta(days=7))
            elif filtro_dashboard == "em_dia":
                stmt = stmt.where(Assinatura.vencimento >= hoje)
'''
        t = trocar(t, marcador, marcador + bloco)
    compile(t, str(p), 'exec')
    arquivos = {p: t}
    p = raiz / 'web/acesso.html'
    t = p.read_text(encoding='utf-8')
    if '<!-- dashboard_usuario_v1 -->' not in t:
        raise RuntimeError('Instale o dashboard primeiro. Nenhum arquivo alterado.')
    if '<!-- paginacao_usuario_v1 -->' not in t:
        t = trocar(t, "pagina=0,ocupado=false;", "pagina=0,porPagina=20,ocupado=false;")
        t = trocar(t, "'/assinaturas?limite=50&deslocamento='+pagina*50", "'/assinaturas?limite='+porPagina+'&deslocamento='+pagina*porPagina")
        t = trocar(t, "(pagina+1)*50>=dados.total", "(pagina+1)*porPagina>=dados.total")
        t = trocar(t, '<button id="proxima">Próxima</button></section>', '<button id="proxima">Próxima</button><label id="tamanhoPaginaBox">Clientes por página <select id="tamanhoPagina"><option value="10">10</option><option value="20" selected>20</option><option value="50">50</option></select></label><p id="resumoPagina" role="status"></p></section>')
        t = trocar(t, "$('anterior').disabled=pagina===0;", "if(!contas)$('resumoPagina').textContent='Mostrando '+(dados.total?pagina*porPagina+1:0)+'–'+Math.min((pagina+1)*porPagina,dados.total)+' de '+dados.total+' clientes';$('anterior').disabled=pagina===0;")
        t = trocar(t, "$('proxima').onclick=", "$('tamanhoPagina').onchange=()=>{const n=Number($('tamanhoPagina').value);if(![10,20,50].includes(n))return;porPagina=n;pagina=0;carregar().catch(e=>$('msg').textContent=e.message)};$('proxima').onclick=")
        t = trocar(t, "$('anterior').hidden=$('proxima').hidden=contas;", "$('anterior').hidden=$('proxima').hidden=contas;$('tamanhoPaginaBox').hidden=contas;$('resumoPagina').hidden=contas;")
        t = t.replace('</html>', '<!-- paginacao_usuario_v1 --></html>', 1)
    if '<!-- filtros_usuario_v1 -->' not in t:
        if t.count('</html>') != 1 or '</script' in js.lower():
            raise RuntimeError('Pagina ou script inesperado. Nenhum arquivo alterado.')
        t = t.replace('</html>', '<!-- filtros_usuario_v1 --><script>' + js + '</script></html>', 1)
    arquivos[p] = t
    backup = raiz / 'backups' / datetime.now().strftime('filtros_paginacao_%Y%m%d_%H%M%S_%f')
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
    print('Filtros e seletor de 10,20,50 clientes instalados. Padrao: 20.')
    print('Nenhum registro, valor ou senha alterado. Backup:', backup)
    print('Reinicie e use Ctrl+F5. Nao execute limpeza de novembro.')

if __name__ == '__main__':
    main()
