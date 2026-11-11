from datetime import date, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import select

from .acesso_login import autenticar
from .database import SessionLocal
from .models import Assinatura

router = APIRouter()


def resumir(linhas, hoje):
    base = [dict(x) for x in linhas if x['status'] != 'CANCELADO']
    operacionais = [x for x in base if x['status'] not in ('INATIVO', 'SUSPENSO') and x['vencimento'] is not None]
    fim7, fim30 = hoje + timedelta(days=7), hoje + timedelta(days=30)
    atrasados = sorted([x for x in operacionais if x['vencimento'] < hoje], key=lambda x: (x['vencimento'], x['id']))
    proximos = sorted([x for x in operacionais if hoje <= x['vencimento'] <= fim30], key=lambda x: (x['vencimento'], x['id']))
    meses = []
    indice = hoje.year * 12 + hoje.month - 1
    for i in range(6):
        ano, mes0 = divmod(indice + i, 12)
        mes = mes0 + 1
        meses.append({'mes': f'{ano:04d}-{mes:02d}', 'quantidade': sum(1 for x in operacionais if x['vencimento'].year == ano and x['vencimento'].month == mes)})
    def item(x):
        return {'id': x['id'], 'nome': x['nome'], 'vencimento': x['vencimento'].isoformat(), 'dias': (x['vencimento'] - hoje).days}
    return {'hoje': hoje.isoformat(), 'total': len(base), 'atrasados': len(atrasados),
            'vence_hoje': sum(1 for x in operacionais if x['vencimento'] == hoje),
            'vence_7_dias': sum(1 for x in operacionais if hoje < x['vencimento'] <= fim7),
            'em_dia': sum(1 for x in operacionais if x['vencimento'] >= hoje),
            'meses': meses, 'proximos': [item(x) for x in proximos[:30]],
            'maiores_atrasos': [item(x) for x in atrasados[:10]]}


@router.get('/auth/vencimentos')
def vencimentos(request: Request):
    autenticar(request)
    with SessionLocal() as db:
        linhas = db.execute(select(Assinatura.id, Assinatura.nome, Assinatura.status, Assinatura.vencimento)).mappings().all()
        return resumir(linhas, date.today())
