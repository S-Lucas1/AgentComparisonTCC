# TCC - Comparacao de agentes de IA: Contexto vs MCP

Esqueleto inicial dos prototipos do TCC.

Compara duas abordagens de interacao com LLMs em tarefa de
suporte a decisao corporativa baseada em dados:

- **Prototipo A (`prototipo_a_contexto`)**: o LLM recebe uma representacao
  textual da base no prompt e responde sem acesso direto.
- **Prototipo B (`prototipo_b_mcp`)**: o LLM tem acesso ao banco via
  ferramenta `executar_sql` (precursora do MCP) e consulta dados reais.

---

## Estrutura

```
tcc-agentes/
├── .env.example               <- copiar para .env e preencher
├── .gitignore
├── requirements.txt
├── data/
│   └── perguntas_exemplo.csv  <- 5 perguntas para testar; as 50 oficiais virao depois
├── resultados/                <- CSVs gerados pelos experimentos
└── src/
    ├── config.py              <- carrega .env e expoe constantes
    ├── db.py                  <- utilitarios de PostgreSQL e schema
    ├── logger.py              <- salva resultados em CSV
    ├── prototipo_a_contexto.py
    ├── prototipo_b_mcp.py
    ├── runner.py              <- roda perguntas nos 2 prototipos
    └── _sanity/
        ├── hello_claude.py    <- testa API Anthropic
        └── hello_db.py        <- testa conexao Olist
```

---

## Como rodar (primeira vez)

### 1. Criar ambiente virtual

```bash
cd tcc-agentes
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Mac/Linux:
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Criar e preencher o `.env`

```bash
# Windows:
copy .env.example .env

# Mac/Linux:
cp .env.example .env
```

Abra o `.env` e:
- Coloque sua chave da Anthropic em `ANTHROPIC_API_KEY` (pegar em https://console.anthropic.com)
- Coloque a senha do PostgreSQL em `DB_PASS`

### 4. Sanity checks

Antes de rodar os prototipos, confirme que tudo esta conectado:

```bash
python -m src._sanity.hello_claude
python -m src._sanity.hello_db
```

Se os dois imprimirem `[OK]`, esta tudo conectado.

### 5. Testar cada prototipo isoladamente

```bash
python -m src.prototipo_a_contexto
python -m src.prototipo_b_mcp
```

Cada comando faz UMA pergunta no respectivo prototipo e mostra o resultado.

### 6. Rodar a bateria de perguntas-exemplo

```bash
python -m src.runner
```

Le `data/perguntas_exemplo.csv`, executa as 5 perguntas nos dois prototipos
e salva tudo em `resultados/resultados_AAAA-MM-DD.csv`.

---

## O que cada arquivo faz (referencia rapida)

| Arquivo | Funcao |
|---------|--------|
| `config.py` | Le o `.env` e expoe constantes (`ANTHROPIC_API_KEY`, `DB_CONFIG`, `MODELO_PADRAO`). Falha cedo se algo estiver faltando. |
| `db.py` | Funcao `executar_sql()` e helpers para descrever schema e estatisticas. Usado pelos dois prototipos. |
| `logger.py` | `salvar_resultado(dict)` anexa uma linha ao CSV do dia. Esquema fixo de colunas. |
| `prototipo_a_contexto.py` | LLM com prompt fixo + contexto da base. Sem ferramentas. |
| `prototipo_b_mcp.py` | LLM com a ferramenta `executar_sql`. Loop ReAct com max 8 iteracoes. |
| `runner.py` | Le CSV de perguntas, executa nos 2 prototipos, salva resultados. |

---

## Custo estimado dos sanity checks

Com Haiku 4.5 (padrao):
- `hello_claude.py`: < 1 centavo de dolar
- `hello_db.py`: zero (nao chama API)
- `prototipo_a` 1 pergunta: ~3-5 centavos (contexto e grande)
- `prototipo_b` 1 pergunta: ~1-2 centavos
- 5 perguntas no runner: ~30 centavos

Para o experimento final com 50 perguntas reais: ver estimativa no README do TCC (~US$ 4 com Haiku, ~US$ 13 com Sonnet).

---

## Pendencias deliberadas (nao sao bugs)

Estes itens estao marcados como TODO no codigo e dependem de decisoes
metodologicas que ainda precisam ser tomadas com o orientador:

1. **Conteudo do contexto do Prototipo A** - hoje so tem schema + estatisticas.
   Pode-se enriquecer com amostras das tabelas, sumarios por categoria, etc.
2. **Migracao do Prototipo B para servidor MCP oficial** - hoje usa tool_use
   direto. A logica e equivalente; muda apenas o protocolo de transporte.
3. **Conjunto de 50 perguntas com gabarito** - hoje so tem 5 de exemplo.
4. **Rubrica de julgamento** - como classificar respostas (correto / parcial /
   incorreto / alucinou / recusou).
5. **Numero de rodadas por pergunta** - LLMs sao estocasticas; o experimento
   final deve rodar cada pergunta 3+ vezes para medir variancia.

---

## Boas praticas de uso

- **NUNCA commite o `.env`** (ja esta no `.gitignore`).
- **Rode sanity checks** antes de qualquer experimento longo.
- **Faca backup do banco** (`pg_dump`) antes de qualquer alteracao.
- **Versione os CSVs de resultados** (mantenha os definitivos no git).
- **Use Haiku para desenvolver**, troque para Sonnet so no experimento final.
