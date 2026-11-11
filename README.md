# API de Assinaturas

API REST (FastAPI + SQLite) para um **agente de IA** gerenciar a base de assinaturas
que hoje vive numa planilha Excel: clientes, planos, vencimentos, renovações,
pagamentos, despesas e auditoria.

> Diagnóstico da planilha original e decisões de arquitetura: [`PLANO.md`](PLANO.md).

## Como funciona

```
Agente de IA  ──HTTP/JSON (OpenAPI)──>  FastAPI  ──>  SQLite (dados/assinaturas.db)
                                            │
                                            ├── importa .xlsb/.xlsx
                                            └── exporta .xlsx
```

O Excel deixa de ser o armazenamento (`.xlsb` só permite leitura com segurança) e passa
a ser **entrada e saída**: importa-se a planilha uma vez e exporta-se quando quiser.

## Instalação

```powershell
cd D:\planilhas
python -m pip install -r requirements.txt
copy .env.example .env      # opcional: ajuste API_KEY
```

### Importar / atualizar a planilha

Fonte oficial: `D:\area  nova\planilha clientes\GERENCIAMENTO DE ASSINATURAS IPTV 86.7 - Copia.xlsb`

```powershell
.\atualizar_base.ps1          # reimporta a planilha oficial
# ou manualmente:
python scripts\importar_planilha.py "D:\area  nova\planilha clientes\GERENCIAMENTO DE ASSINATURAS IPTV 86.7 - Copia.xlsb"
```

Opções: `--aba "BASE DE DADOS"`, `--aba-planos "PLANOS E VALORES"`,
`--recalcular-status` (define ATIVO/INATIVO pela data de vencimento em vez de copiar a coluna).

O comando é **idempotente**: rodar de novo atualiza os registros existentes
(chave = ID + nome) em vez de duplicar. Rodar `atualizar_base.ps1` depois de
qualquer edição no Excel mantém o banco alinhado.

### Subir a API

```powershell
.\start.ps1
# ou: python -m uvicorn app.main:app --reload
```

- **Painel visual: http://127.0.0.1:8000/painel**
- API: http://127.0.0.1:8000
- Documentação interativa (Swagger): http://127.0.0.1:8000/docs
- OpenAPI (o que o agente consome): http://127.0.0.1:8000/openapi.json

O painel (`web/painel.html`) é um arquivo único, sem dependências externas. Para
personalizar: `CONFIG` (título, janela de dias, quantidades) no JavaScript e as
cores nas variáveis `:root` do CSS. Ele pede a `X-API-Key` uma vez e guarda no navegador.

O `start.ps1` sobe apenas em `127.0.0.1` (acessível só nesta máquina) e, se o banco
não existir, importa a planilha oficial automaticamente.

## Autenticação

Todas as rotas (exceto `/health`) exigem o header:

```
X-API-Key: <API_KEY>
```

Defina `API_KEY` no `.env` ou no ambiente. O padrão `dev-local-troque-esta-chave`
serve só para desenvolvimento.

## Painel visual

Em **http://127.0.0.1:8000/painel**:

- indicadores (total, em atraso, vencendo, ativas) e financeiro (carteira, recebido, despesas, lucro);
  os cartões de indicadores são clicáveis e abrem a lista já filtrada;
- gráficos de produto, plano, atraso por faixa e vencimentos por mês;
- **+ Novo cliente** — cadastra nome, contato, usuário/senha, plano, valor, desconto e vencimento
  (o plano preenche valor e data automaticamente);
- **lista de clientes** com busca, filtros e ações por linha:
  - **Renovar** — informa dias, valor e forma de pagamento (gera lançamento financeiro);
  - **Editar** — abre os dados do cliente preenchidos (nome, contato, usuário/senha,
    plano, valor, desconto, vencimento, observação) e salva via `PATCH`;
  - **Ativar / Suspender** — alterna o status;
  - **WhatsApp** — abre `wa.me` com mensagem pronta e editável;
  - **Excluir** — cancela a assinatura (soft delete, some da lista padrão).

As mensagens do WhatsApp ficam em `CONFIG.mensagens` no `web/painel.html`:
`padrao` vale para todos; `vencida` e `aVencer` são opcionais. Variáveis:
`{nome}`, `{plano}`, `{vencimento}`, `{valor}`, `{dias}`. Use `*texto*` para negrito
no WhatsApp.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | status do serviço |
| GET | `/assinaturas` | lista com filtros: `q`, `status`, `produto`, `plano`, `situacao`, `vencendo_em_dias`, `atrasadas`, `limite`, `deslocamento` |
| GET | `/assinaturas/{id}` | detalhe + credenciais |
| POST | `/assinaturas` | cria assinatura (calcula valor final, vencimento e lucro) |
| PATCH | `/assinaturas/{id}` | atualiza campos |
| DELETE | `/assinaturas/{id}` | cancela (soft delete) |
| POST | `/assinaturas/{id}/renovar` | renova por N dias e lança a receita |
| POST | `/assinaturas/{id}/pagamentos` | registra pagamento avulso |
| GET | `/assinaturas/{id}/lancamentos` | histórico financeiro |
| POST | `/assinaturas/{id}/suspender` \| `/reativar` | muda status operacional |
| GET/POST | `/planos` | catálogo de planos |
| GET/PATCH/DELETE | `/planos/{id}` | manutenção do catálogo |
| GET | `/dashboard` | total, ativas, vencidas, MRR, recebido/despesas/lucro do mês, por produto/plano |
| GET | `/vencimentos?dias=7` | quem vence nos próximos N dias |
| GET | `/inadimplentes` | vencidas e em dia (com dias de atraso) |
| GET/POST | `/lancamentos` | receitas e despesas |
| GET | `/eventos` | auditoria de tudo que foi alterado |
| POST | `/admin/importacao/excel` | upload de `.xlsb/.xlsx` e importação |
| GET | `/admin/exportacao/excel` | baixa a base atual em `.xlsx` |

`situacao` aceita: `ativa`, `vencendo`, `vencida`, `vence_hoje`, `inativa`,
`suspensa`, `cancelada`, `sem_vencimento`.

## Exemplos

```powershell
$h = @{ "X-API-Key" = "dev-local-troque-esta-chave" }

# quem vence nos próximos 7 dias
Invoke-RestMethod "http://127.0.0.1:8000/vencimentos?dias=7" -Headers $h | ConvertTo-Json -Depth 5

# criar assinatura
$corpo = @{
  nome = "MARIA SILVA"; contato = "11 99999-0000"; plano_nome = "MENSAL 30"
  forma_pagamento = "PIX"
  credenciais = @(@{ ordem = 1; usuario = "maria"; senha = "1234" })
} | ConvertTo-Json -Depth 5
Invoke-RestMethod "http://127.0.0.1:8000/assinaturas" -Method Post -Headers $h -ContentType "application/json" -Body $corpo

# renovar
Invoke-RestMethod "http://127.0.0.1:8000/assinaturas/1/renovar" -Method Post -Headers $h `
  -ContentType "application/json" -Body '{"dias":30,"valor":30,"forma_pagamento":"PIX"}'
```

## Estrutura

```
app/
  main.py            aplicação FastAPI
  config.py          variáveis de ambiente
  database.py        engine/sessão SQLite
  models.py          Plano, Assinatura, Credencial, Lancamento, Evento
  schemas.py         contratos (Pydantic)
  importer.py        leitura .xlsb/.xlsx -> banco
  exporter.py        banco -> .xlsx
  security.py        X-API-Key
  auditoria.py       log de alterações
  routers/           assinaturas, planos, relatorios, admin
web/painel.html      painel visual (HTML/CSS/JS unico)
scripts/             importar / exportar via linha de comando
tests/               testes da API
dados/               banco SQLite (gerado)
start.ps1            sobe a API (local)
atualizar_base.ps1   reimporta a planilha oficial
```

## Testes

```powershell
python -m pytest tests -q
```
