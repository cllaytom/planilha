"""Geracao de uma planilha .xlsx a partir do banco (para relatorios/backup)."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assinatura, Plano

CABECALHOS = [
    "ID", "Nome", "Usuario", "Contato", "Data Cadastro", "Status", "Produto", "Plano",
    "Valor", "Conexoes", "Desconto", "Valor Final", "Vencimento", "For. Pagamento",
    "Dia Cobranca", "Observacao", "Custo", "Lucro", "Situacao", "Dias",
]


def _estilizar(ws, larguras: dict[int, int]) -> None:
    cabecalho = PatternFill("solid", fgColor="1F3864")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = cabecalho
    for coluna, largura in larguras.items():
        ws.column_dimensions[get_column_letter(coluna)].width = largura
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def gerar_xlsx(db: Session) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "BASE DE DADOS"
    ws.append(CABECALHOS)

    assinaturas = db.scalars(select(Assinatura).order_by(Assinatura.nome)).all()
    for ass in assinaturas:
        ws.append([
            ass.codigo_legado, ass.nome, ass.usuario, ass.contato, ass.data_cadastro,
            ass.status, ass.produto, ass.plano_nome, ass.valor, ass.conexoes,
            ass.desconto, ass.valor_final, ass.vencimento, ass.forma_pagamento,
            ass.dia_cobranca, ass.observacao, ass.custo, ass.lucro, ass.situacao,
            ass.dias_atraso,
        ])
    _estilizar(ws, {1: 8, 2: 26, 3: 20, 4: 20, 5: 14, 6: 12, 7: 16, 8: 16,
                    9: 10, 10: 10, 11: 10, 12: 12, 13: 12, 14: 14, 15: 12,
                    16: 40, 17: 10, 18: 10, 19: 14, 20: 8})

    ws_planos = wb.create_sheet("PLANOS E VALORES")
    ws_planos.append(["Plano", "Produto", "Valor", "Dias", "Conexoes",
                      "Valor Custo", "Servidor", "DNS", "Ativo"])
    for plano in db.scalars(select(Plano).order_by(Plano.nome)).all():
        ws_planos.append([plano.nome, plano.produto, plano.valor, plano.dias,
                          plano.conexoes, plano.valor_custo, plano.servidor,
                          plano.dns, "SIM" if plano.ativo else "NAO"])
    _estilizar(ws_planos, {1: 20, 2: 16, 3: 10, 4: 8, 5: 10, 6: 12, 7: 20, 8: 28, 9: 8})

    ws_cred = wb.create_sheet("CREDENCIAIS")
    ws_cred.append(["ID Assinatura", "Cliente", "Ordem", "Usuario", "Senha",
                    "Servidor", "Sistema", "Produto", "URL", "MAC", "Device Key",
                    "Ativacao App", "Vencimento App", "Aplicativo"])
    for ass in assinaturas:
        for c in ass.credenciais:
            ws_cred.append([ass.id, ass.nome, c.ordem, c.usuario, c.senha, c.servidor,
                            c.sistema, c.produto, c.url, c.mac, c.device_key,
                            c.ativacao_app, c.vencimento_app, c.aplicativo])
    _estilizar(ws_cred, {1: 12, 2: 26, 3: 8, 4: 22, 5: 18, 6: 14, 7: 14, 8: 14,
                         9: 26, 10: 18, 11: 22, 12: 14, 13: 14, 14: 14})

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
