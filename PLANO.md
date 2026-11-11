# API de Gerenciamento de Assinaturas — Plano

## 1. Situação atual (diagnóstico)

- A pasta `D:\planilhas` está vazia.
- **Fonte oficial (definida pelo usuário):**
  `D:\area  nova\planilha clientes\GERENCIAMENTO DE ASSINATURAS IPTV 86.7 - Copia.xlsb`
- Outros candidatos descartados:
  - `D:\area  nova\IPTV\GERENCIAMENTO DE ASSINATURAS IPTV 86.7.xlsb` — abas de dados vazias.
  - `D:\area  nova\planilha clientes\Gerenciamento Clientes 2024.xlsb` — mesmos 341 clientes da oficial.
- Todos são `.xlsb` (Excel binário) **com macros VBA** (projeto VBA de ~29 MB no 86.7).

### Estrutura de colunas já identificada (aba `BASE DE DADOS`, linha 22)

```
ID | Nome | Usuario | Contato | Data Cadastro | Status | Produto | Plano | Valor |
Conexões | Desconto | Valor Final | Cobrança | Vencimento | For. Pagamento | Mês |
Status Vencimento | Dias | Mês2 | Nome de 3º | Ano | Senha | Servidor | Sistema |
Observação | 2º Usuario | 2º Senha | 3º Usuario | 3º Senha | 4º Usuario | 4º Senha |
Sistema 02 | Sistema 03 | Sistema 04 | Servidor2..4 | Produto 02..04 | ST | CX | DNS | Custo | Lucro
```

Abas auxiliares: `PLANOS E VALORES`, `ESTOQUE_CRED`, `FORNECEDORES`, `VENDEDOR`,
`APLICATIVOS`, `HISTÓRICO DE VENDAS`, `FATURAMENTO`, `DASHBOARD`, `RELATÓRIO`.

## 2. Decisão de arquitetura

**Recomendado: banco de dados como fonte da verdade (SQLite) + importação/exportação Excel.**

Motivos:
1. `.xlsb` é **somente leitura** nas bibliotecas Python (`pyxlsb`) — não existe escrita confiável.
   Escrever exigiria automação do Excel (COM/`pywin32`), que é lento, trava com arquivo aberto
   e pode corromper o arquivo.
2. API + agente de IA precisam de validação, concorrência e histórico de alterações.
3. O Excel continua disponível via **exportação** (`.xlsx`) para relatórios/visualização.

```
Agente de IA  ──HTTP/JSON (OpenAPI)──>  FastAPI  ──>  SQLite
                                            │
                                            ├── importar .xlsb/.xlsx
                                            └── exportar .xlsx
```

Stack: **Python 3.13 + FastAPI + SQLModel/SQLAlchemy + SQLite + openpyxl**.

## 3. Modelo de dados (núcleo)

- `cliente`: id, nome, contato, documento, observacao, criado_em
- `assinatura`: id, cliente_id, produto, plano_id, valor, desconto, valor_final,
  status (ativa | vencida | suspensa | cancelada | teste), data_cadastro,
  vencimento, forma_pagamento, servidor, sistema, usuario, senha,
  conexoes, custo, lucro
- `credencial_extra`: assinatura_id, ordem (2..4), usuario, senha, servidor, sistema, produto
- `plano`: nome, produto, valor, duracao_dias, conexoes
- `pagamento` / `renovacao`: assinatura_id, data, valor, forma_pagamento, tipo
- `fornecedor`, `estoque_credito`, `vendedor`, `aplicativo`
- `evento` (auditoria): entidade, entidade_id, acao, antes, depois, origem (api/agente/humano)

## 4. Endpoints principais

| Método | Rota | Uso pelo agente |
|---|---|---|
| GET | `/assinaturas` | listar com filtros (`status`, `vencendo_em_dias`, `q`, paginação) |
| POST | `/assinaturas` | criar assinatura |
| GET | `/assinaturas/{id}` | detalhe |
| PATCH | `/assinaturas/{id}` | atualizar campos |
| DELETE | `/assinaturas/{id}` | cancelar (soft delete) |
| POST | `/assinaturas/{id}/renovar` | renovar (gera pagamento e novo vencimento) |
| POST | `/assinaturas/{id}/suspender` | suspender/reativar |
| GET | `/clientes`, `/clientes/{id}` | consulta por nome/contato |
| GET | `/planos` | catálogo de planos e preços |
| GET | `/vencimentos?dias=7` | quem vence nos próximos N dias |
| GET | `/inadimplentes` | atrasados + dias em atraso |
| GET | `/dashboard` | ativos, MRR, recebido no mês, custo, lucro |
| GET | `/estoque` | créditos por fornecedor |
| POST | `/importacao/excel` | importar planilha |
| GET | `/exportacao/excel` | gerar `.xlsx` da base |
| GET | `/health` | status |

Autenticação: header `X-API-Key` (chave por agente/integração) + log de auditoria em toda escrita.

## 5. Fases de entrega

1. **Extração** — ler a planilha correta, mapear colunas → CSV/SQLite, relatório de qualidade
   (duplicados, datas inválidas, status desconhecidos).
2. **API somente leitura** — listagens, filtros, dashboard, `/openapi.json`.
3. **CRUD + validações** — regras de negócio (renovação, desconto, status).
4. **Excel** — exportação `.xlsx` e importação incremental.
5. **Integração com o agente** — OpenAPI + (opcional) servidor MCP com as mesmas operações.

## 6. Status da implementação (MVP entregue)

Já funciona em `D:\planilhas`:

- [x] Banco SQLite (`dados/assinaturas.db`) com `planos`, `assinaturas`, `credenciais`,
      `lancamentos` e `eventos` (auditoria).
- [x] Importação da planilha oficial
      **`D:\area  nova\planilha clientes\GERENCIAMENTO DE ASSINATURAS IPTV 86.7 - Copia.xlsb`**:
      341 assinaturas únicas (358 linhas, 17 duplicadas), 38 planos, credenciais 1–5,
      colunas extras preservadas em `dados_extras`. As duas planilhas candidatas
      (2024 e "Copia") têm exatamente os mesmos 341 clientes.
- [x] CRUD de assinaturas e planos, renovação, pagamentos, suspensão/reativação.
- [x] Relatórios: dashboard, vencimentos, inadimplentes, lançamentos, auditoria.
- [x] Exportação `.xlsx` (base, planos e credenciais).
- [x] Autenticação `X-API-Key` + OpenAPI em `/docs` e `/openapi.json`.
- [x] Painel visual (`/painel`) com indicadores, gráficos, lista de clientes,
      renovação, ativar/suspender, cancelar e mensagem pronta no WhatsApp.
- [x] 4 testes automatizados passando.

Próximos passos sugeridos:

1. Servidor MCP expondo as mesmas operações (ferramentas nativas para o agente).
2. Agendamento diário: recalcular status e gerar lista de cobrança/WhatsApp.
3. Backup automático do SQLite e exportação periódica em `.xlsx`.
4. Migrar para Postgres se houver mais de um usuário/instância acessando.

## 7. Decisões e pendências

- [x] Base oficial: `GERENCIAMENTO DE ASSINATURAS IPTV 86.7 - Copia.xlsb`.
- [x] Uso **somente local** (`127.0.0.1`); sem exposição na internet por enquanto.
- [x] Regra de renovação: usa `dias` do plano (30 por padrão; 7 no plano semanal),
      contando a partir de hoje ou do vencimento atual, o que for maior.
- [ ] O Excel será usado no futuro? (indefinido — por isso a exportação e a
      reimportação idempotente já estão prontas)
- [ ] Recalcular o status (ATIVO/INATIVO) pela data de vencimento na importação?
      Hoje a planilha vem com todos os 341 registros como INATIVO (dados de 2024).
