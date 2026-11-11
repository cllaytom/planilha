"""Leitura da planilha original (.xlsb/.xlsx) para o banco da API."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assinatura, Credencial, Plano
from .utils import (
    chave_header,
    como_float,
    como_int,
    como_texto,
    excel_para_data,
    limpar,
)

# campos da API -> possiveis cabecalhos na planilha (ja normalizados)
MAPA_PRINCIPAL = {
    "codigo_legado": ["ID"],
    "nome": ["NOME"],
    "usuario": ["USUARIO"],
    "contato": ["CONTATO"],
    "data_cadastro": ["DATACADASTRO"],
    "status": ["STATUS"],
    "produto": ["PRODUTO"],
    "plano_nome": ["PLANO"],
    "valor": ["VALOR"],
    "conexoes": ["CONEXOES"],
    "desconto": ["DESCONTO"],
    "valor_final": ["VALORFINAL"],
    "forma_pagamento": ["FORPAGAMENTO", "FORMAPAGAMENTO"],
    "vencimento": ["VENCIMENTO"],
    "dia_cobranca": ["DIACOBRANCA"],
    "observacao": ["OBSERVACAO"],
    "custo": ["CUSTO"],
    "lucro": ["LUCRO"],
    "indicado_por": ["INDICADO"],
}

CAMPOS_DATA = {"data_cadastro", "vencimento"}
CAMPOS_INT = {"conexoes", "dia_cobranca"}
CAMPOS_FLOAT = {"valor", "desconto", "valor_final", "custo", "lucro"}

# credenciais por ordem: (sufixo de coluna)
SUFIXOS_CREDENCIAL = {
    1: {"usuario": "USUARIO", "senha": "SENHA", "servidor": "SERVIDOR",
        "sistema": "SISTEMA", "mac": "MAC", "device_key": "DEVICEKEY",
        "ativacao_app": "ATIVACAOAPP1", "vencimento_app": "VENCIMENTOAPP1"},
    2: {"usuario": "2OUSUARIO", "senha": "2OSENHA", "servidor": "SERVIDOR2",
        "sistema": "SISTEMA02", "produto": "PRODUTO02", "url": "URL2",
        "mac": "MAC2", "device_key": "DEVICEKEY2",
        "ativacao_app": "ATIVACAOAPP2", "vencimento_app": "VENCIMENTOAPP2",
        "aplicativo": "APLICATIVO2"},
    3: {"usuario": "3OUSUARIO", "senha": "3OSENHA", "servidor": "SERVIDOR3",
        "sistema": "SISTEMA03", "produto": "PRODUTO03", "url": "URL3",
        "mac": "MAC3", "device_key": "DEVICEKEY3",
        "ativacao_app": "ATIVACAOAPP3", "vencimento_app": "VENCIMENTOAPP3",
        "aplicativo": "APLICATIVO3"},
    4: {"usuario": "4OUSUARIO", "senha": "4OSENHA", "servidor": "SERVIDOR4",
        "sistema": "SISTEMA04", "produto": "PRODUTO04", "url": "URL4",
        "mac": "MAC4", "device_key": "DEVICEKEY4",
        "ativacao_app": "ATIVACAOAPP4", "vencimento_app": "VENCIMENTOAPP4",
        "aplicativo": "APLICATIVO4"},
    5: {"usuario": "5OUSUARIO", "senha": "5OSENHA", "servidor": "5OSERVIDOR",
        "sistema": "5OSISTEMA", "produto": "5OPRODUTO", "url": "URL5",
        "mac": "MAC5", "device_key": "DEVICEKEY5",
        "ativacao_app": "ATIVACAOAPP5", "vencimento_app": "VENCIMENTOAPP5",
        "aplicativo": "APLICATIVO5"},
}

MAPA_PLANO = {
    "nome": ["PLANO"],
    "valor": ["VALORREVENDA"],
    "dias": ["DIAS"],
    "conexoes": ["CONEXOES"],
    "produto": ["PRODUTO"],
    "servidor": ["SERVIDORIPTVP2P"],
    "valor_custo": ["VALORDECUSTO"],
    "dns": ["URLDNS"],
}


def ler_linhas(caminho: Path, aba: str) -> list[list]:
    sufixo = caminho.suffix.lower()
    if sufixo == ".xlsb":
        from pyxlsb import open_workbook

        with open_workbook(str(caminho)) as wb:
            if aba not in wb.sheets:
                raise ValueError(f"Aba '{aba}' nao encontrada. Abas: {wb.sheets}")
            with wb.get_sheet(aba) as sheet:
                return [[c.v for c in row] for row in sheet.rows()]
    if sufixo in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        wb = load_workbook(str(caminho), read_only=True, data_only=True)
        try:
            if aba not in wb.sheetnames:
                raise ValueError(f"Aba '{aba}' nao encontrada. Abas: {wb.sheetnames}")
            return [list(row) for row in wb[aba].iter_rows(values_only=True)]
        finally:
            wb.close()
    raise ValueError(f"Formato nao suportado: {sufixo}")


def _indice_cabecalho(linhas: list[list], exigidos: set[str]) -> tuple[int, dict[str, int], dict[str, str]]:
    for i, linha in enumerate(linhas[:60]):
        colunas = {chave_header(v): j for j, v in enumerate(linha) if limpar(v) is not None}
        if exigidos.issubset(colunas):
            rotulos = {
                chave_header(v): str(v).strip() for v in linha if limpar(v) is not None
            }
            return i, colunas, rotulos
    raise ValueError(f"Cabecalho com {exigidos} nao encontrado nas primeiras 60 linhas.")


def _valor(linha, colunas, nomes):
    for nome in nomes:
        j = colunas.get(nome)
        if j is not None and j < len(linha):
            v = limpar(linha[j])
            if v is not None:
                return v
    return None


def _converter(campo, valor):
    if campo in CAMPOS_DATA:
        return excel_para_data(valor)
    if campo in CAMPOS_INT:
        return como_int(valor)
    if campo in CAMPOS_FLOAT:
        return como_float(valor)
    if campo == "codigo_legado" and isinstance(valor, (int, float)):
        return str(int(valor))  # a planilha guarda o ID como numero (647.0)
    return como_texto(valor)


def _completar_planos(linhas, inicio, colunas, db: Session, planos: dict[str, Plano]) -> int:
    """Cria planos citados nas assinaturas mas ausentes na aba de catalogo."""
    amostras: dict[str, list[tuple[float, str | None]]] = defaultdict(list)
    for linha in linhas[inicio + 1:]:
        if not como_texto(_valor(linha, colunas, MAPA_PRINCIPAL["nome"])):
            continue
        nome_plano = como_texto(_valor(linha, colunas, MAPA_PRINCIPAL["plano_nome"]))
        if not nome_plano:
            continue
        amostras[nome_plano].append((
            como_float(_valor(linha, colunas, MAPA_PRINCIPAL["valor"])),
            como_texto(_valor(linha, colunas, MAPA_PRINCIPAL["produto"])),
        ))

    criados = 0
    for nome_plano, itens in amostras.items():
        if nome_plano.upper() in planos:
            continue
        valor = Counter(v for v, _ in itens).most_common(1)[0][0]
        produtos = Counter(p for _, p in itens if p).most_common(1)
        dias = 7 if ("SEMANAL" in nome_plano.upper() or re.search(r"\b7\b", nome_plano)) else 30
        plano = Plano(
            nome=nome_plano,
            produto=produtos[0][0] if produtos else None,
            valor=valor,
            dias=dias,
        )
        db.add(plano)
        db.flush()
        planos[nome_plano.upper()] = plano
        criados += 1
    return criados


def _chave(nome: str, codigo: str | None) -> tuple[str, str]:
    return ((codigo or "").strip(), (nome or "").strip().upper())


def importar_planos(linhas: list[list], db: Session) -> int:
    try:
        inicio, colunas, _rotulos = _indice_cabecalho(linhas, {"PLANO", "DIAS", "PRODUTO"})
    except ValueError:
        return 0

    existentes = {p.nome.upper(): p for p in db.scalars(select(Plano)).all()}
    criados = 0
    for linha in linhas[inicio + 1:]:
        nome = como_texto(_valor(linha, colunas, MAPA_PLANO["nome"]))
        if not nome:
            continue
        dados = {
            "produto": como_texto(_valor(linha, colunas, MAPA_PLANO["produto"])),
            "valor": como_float(_valor(linha, colunas, MAPA_PLANO["valor"])),
            "dias": como_int(_valor(linha, colunas, MAPA_PLANO["dias"]), 30),
            "conexoes": como_int(_valor(linha, colunas, MAPA_PLANO["conexoes"]), 1),
            "servidor": como_texto(_valor(linha, colunas, MAPA_PLANO["servidor"])),
            "valor_custo": como_float(_valor(linha, colunas, MAPA_PLANO["valor_custo"])),
            "dns": como_texto(_valor(linha, colunas, MAPA_PLANO["dns"])),
        }
        plano = existentes.get(nome.upper())
        if plano:
            for campo, valor in dados.items():
                setattr(plano, campo, valor)
        else:
            plano = Plano(nome=nome, **dados)
            db.add(plano)
            existentes[nome.upper()] = plano
            criados += 1
        db.flush()
    return criados


def _montar_credenciais(linha, colunas) -> list[Credencial]:
    credenciais = []
    for ordem, mapa in SUFIXOS_CREDENCIAL.items():
        dados = {}
        for campo, sufixo in mapa.items():
            bruto = _valor(linha, colunas, [sufixo])
            if bruto is None:
                continue
            dados[campo] = excel_para_data(bruto) if campo in ("ativacao_app", "vencimento_app") else como_texto(bruto)
        if any(dados.get(c) for c in ("usuario", "senha", "mac", "device_key")):
            credenciais.append(Credencial(ordem=ordem, **dados))
    return credenciais


def importar_planilha(
    caminho: str | Path,
    db: Session,
    aba: str = "BASE DE DADOS",
    aba_planos: str = "PLANOS E VALORES",
    recalcular_status: bool = False,
) -> dict:
    caminho = Path(caminho)
    resultado = {
        "linhas_lidas": 0,
        "criados": 0,
        "atualizados": 0,
        "ignorados": 0,
        "planos_criados": 0,
        "erros": [],
    }

    try:
        linhas_planos = ler_linhas(caminho, aba_planos)
        resultado["planos_criados"] = importar_planos(linhas_planos, db)
    except Exception as exc:  # planos sao opcionais
        resultado["erros"].append(f"planos: {exc}")

    linhas = ler_linhas(caminho, aba)
    inicio, colunas, rotulos = _indice_cabecalho(linhas, {"ID", "NOME"})

    existentes: dict[tuple[str, str], Assinatura] = {}
    for ass in db.scalars(select(Assinatura)).all():
        existentes[_chave(ass.nome, ass.codigo_legado)] = ass

    planos = {p.nome.upper(): p for p in db.scalars(select(Plano)).all()}
    resultado["planos_criados"] += _completar_planos(linhas, inicio, colunas, db, planos)

    for numero, linha in enumerate(linhas[inicio + 1:], start=inicio + 2):
        nome = como_texto(_valor(linha, colunas, MAPA_PRINCIPAL["nome"]))
        if not nome:
            if any(limpar(v) is not None for v in linha):
                resultado["ignorados"] += 1
            continue
        resultado["linhas_lidas"] += 1
        try:
            valores = {}
            for campo, nomes in MAPA_PRINCIPAL.items():
                bruto = _valor(linha, colunas, nomes)
                valores[campo] = _converter(campo, bruto)

            valores.pop("nome", None)  # nome vai como argumento explicito abaixo

            if not valores.get("valor_final"):
                valores["valor_final"] = (valores.get("valor") or 0.0) - (valores.get("desconto") or 0.0)
            if valores.get("lucro") in (None, 0.0):
                valores["lucro"] = valores["valor_final"] - (valores.get("custo") or 0.0)
            if not valores.get("data_cadastro"):
                valores["data_cadastro"] = date.today()
            if not valores.get("status"):
                valores["status"] = "ATIVO"
            if recalcular_status:
                venc = valores.get("vencimento")
                valores["status"] = "ATIVO" if venc and venc >= date.today() else "INATIVO"

            plano = planos.get((valores.get("plano_nome") or "").upper())
            if plano:
                valores["plano_id"] = plano.id

            # colunas nao mapeadas ficam preservadas em dados_extras
            extras = {}
            usados = set()
            for nomes in MAPA_PRINCIPAL.values():
                usados.update(nomes)
            for sufixos in SUFIXOS_CREDENCIAL.values():
                usados.update(sufixos.values())
            for cabecalho, j in colunas.items():
                if cabecalho in usados or j >= len(linha):
                    continue
                v = limpar(linha[j])
                if v is not None:
                    extras[rotulos.get(cabecalho, cabecalho)] = str(v)[:200]
            valores["dados_extras"] = extras

            chave = _chave(nome, valores.get("codigo_legado"))
            ass = existentes.get(chave)
            if ass:
                for campo, valor in valores.items():
                    setattr(ass, campo, valor)
                ass.credenciais.clear()
                ass.credenciais.extend(_montar_credenciais(linha, colunas))
                resultado["atualizados"] += 1
            else:
                ass = Assinatura(nome=nome, **valores)
                ass.credenciais = _montar_credenciais(linha, colunas)
                db.add(ass)
                existentes[chave] = ass
                resultado["criados"] += 1
        except Exception as exc:
            resultado["erros"].append(f"linha {numero}: {exc}")

    db.commit()
    return resultado
