import os
import tempfile
from datetime import date, timedelta

_tmp = tempfile.mkdtemp(prefix="api-assinaturas-teste-")
os.environ["DATA_DIR"] = _tmp
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/teste.db"
os.environ["API_KEY"] = "chave-de-teste"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)
cliente = TestClient(app)
HEADERS = {"X-API-Key": "chave-de-teste"}


def test_health():
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_painel_visual():
    resposta = cliente.get("/painel")
    assert resposta.status_code == 200
    assert "Painel de Assinaturas" in resposta.text


def test_exige_api_key():
    assert cliente.get("/assinaturas").status_code == 401
    assert cliente.get("/assinaturas", headers={"X-API-Key": "errada"}).status_code == 401


def test_fluxo_completo():
    plano = cliente.post(
        "/planos",
        headers=HEADERS,
        json={"nome": "MENSAL 30", "valor": 30.0, "dias": 30, "produto": "IPTV"},
    )
    assert plano.status_code == 201, plano.text
    plano_id = plano.json()["id"]

    criada = cliente.post(
        "/assinaturas",
        headers=HEADERS,
        json={
            "nome": "CLIENTE TESTE",
            "usuario": "cliente.teste",
            "contato": "11 90000-0000",
            "plano_nome": "MENSAL 30",
            "desconto": 5.0,
            "credenciais": [{"ordem": 1, "usuario": "cliente.teste", "senha": "1234"}],
        },
    )
    assert criada.status_code == 201, criada.text
    assinatura = criada.json()
    assert assinatura["valor_final"] == 25.0
    assert assinatura["situacao"] == "ativa"
    assert assinatura["vencimento"] == (date.today() + timedelta(days=30)).isoformat()
    assert len(assinatura["credenciais"]) == 1

    assinatura_id = assinatura["id"]

    listagem = cliente.get("/assinaturas", headers=HEADERS, params={"q": "teste"})
    assert listagem.status_code == 200
    assert listagem.json()["total"] == 1

    detalhe = cliente.get(f"/assinaturas/{assinatura_id}", headers=HEADERS)
    assert detalhe.status_code == 200
    assert detalhe.json()["plano_id"] == plano_id

    atualizada = cliente.patch(
        f"/assinaturas/{assinatura_id}",
        headers=HEADERS,
        json={"contato": "11 91111-1111", "valor": 40.0},
    )
    assert atualizada.status_code == 200
    assert atualizada.json()["contato"] == "11 91111-1111"
    assert atualizada.json()["valor_final"] == 35.0

    renovada = cliente.post(
        f"/assinaturas/{assinatura_id}/renovar",
        headers=HEADERS,
        json={"dias": 30, "valor": 40.0, "forma_pagamento": "PIX"},
    )
    assert renovada.status_code == 200, renovada.text
    assert renovada.json()["vencimento_novo"] == (date.today() + timedelta(days=60)).isoformat()

    pagamento = cliente.post(
        f"/assinaturas/{assinatura_id}/pagamentos",
        headers=HEADERS,
        json={"valor": 10.0, "descricao": "adiantamento"},
    )
    assert pagamento.status_code == 201

    historico = cliente.get(f"/assinaturas/{assinatura_id}/lancamentos", headers=HEADERS)
    assert len(historico.json()) == 2

    suspensa = cliente.post(f"/assinaturas/{assinatura_id}/suspender", headers=HEADERS)
    assert suspensa.json()["situacao"] == "suspensa"
    reativada = cliente.post(f"/assinaturas/{assinatura_id}/reativar", headers=HEADERS)
    assert reativada.json()["situacao"] in ("ativa", "vencendo")

    dashboard = cliente.get("/dashboard", headers=HEADERS)
    assert dashboard.status_code == 200
    assert dashboard.json()["total"] == 1
    assert dashboard.json()["ativas"] == 1

    inadimplentes = cliente.get("/inadimplentes", headers=HEADERS)
    assert inadimplentes.status_code == 200

    eventos = cliente.get("/eventos", headers=HEADERS)
    assert eventos.status_code == 200
    assert eventos.json()["total"] >= 4

    exportado = cliente.get("/admin/exportacao/excel", headers=HEADERS)
    assert exportado.status_code == 200
    assert exportado.content[:2] == b"PK"

    cancelada = cliente.delete(f"/assinaturas/{assinatura_id}", headers=HEADERS)
    assert cancelada.json()["status"] == "CANCELADO"
    assert cancelada.json()["situacao"] == "cancelada"


def test_filtros_de_vencimento():
    criada = cliente.post(
        "/assinaturas",
        headers=HEADERS,
        json={
            "nome": "CLIENTE VENCIDO",
            "vencimento": (date.today() - timedelta(days=10)).isoformat(),
        },
    )
    assert criada.status_code == 201, criada.text
    vencidas = cliente.get("/assinaturas", headers=HEADERS, params={"situacao": "vencida"})
    assert vencidas.json()["total"] == 1
    assert vencidas.json()["itens"][0]["dias_atraso"] == 10
