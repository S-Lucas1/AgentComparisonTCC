"""
================================================================================
BASELINE — VERSAO COM TOOL_USE DIRETO DA API ANTHROPIC
================================================================================
Versao de baseline com tool_use direto da API Anthropic.
Mantida para referencia historica do TCC.
NAO use em experimentos finais; use prototipo_b_mcp.py (que usa MCP real,
com protocolo JSON-RPC sobre stdio entre cliente Python e servidor Node.js).
================================================================================

PROTOTIPO B - LLM COM ACESSO AO BANCO VIA FERRAMENTA SQL
=========================================================

A LLM recebe uma ferramenta `executar_sql` e usa em loop para
consultar dados reais antes de responder.

NOTA SOBRE MCP:
O TCC compara 'contexto puro' vs 'MCP'. Esta implementacao usa
TOOL USE direto da API Anthropic, que e o mecanismo subjacente
ao MCP. Para fidelidade total ao TCC, a etapa final do experimento
devera migrar para o servidor MCP oficial da Anthropic
(github.com/modelcontextprotocol/servers/tree/main/src/postgres),
mas a logica de loop ReAct e identica - so muda o protocolo de transporte
das ferramentas. Esta e uma decisao a documentar no Capitulo 3.
"""
import time
from anthropic import Anthropic

from src.config import ANTHROPIC_API_KEY, MODELO_PADRAO
from src.db import executar_sql, obter_schema_resumido


_cliente = Anthropic(api_key=ANTHROPIC_API_KEY)
_schema_cache: str | None = None


# === Definicao da ferramenta exposta ao LLM ===
FERRAMENTA_SQL = {
    "name": "executar_sql",
    "description": (
        "Executa uma query SQL (SELECT) no banco PostgreSQL Olist e retorna o resultado. "
        "Use sempre que precisar de dados reais para responder. "
        "NAO use para INSERT, UPDATE ou DELETE - apenas leitura."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "Query SQL a executar. Apenas SELECT.",
            }
        },
        "required": ["sql"],
    },
}


def _system_prompt() -> str:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = obter_schema_resumido()

    return f"""Voce e um analista de dados respondendo perguntas sobre uma base \
de e-commerce brasileira (Olist).

VOCE TEM ACESSO AO BANCO via a ferramenta `executar_sql`.

REGRAS IMPORTANTES:
1. SEMPRE busque dados reais via `executar_sql` antes de responder.
2. Se a pergunta nao puder ser respondida com os dados (ex: dado fora da
   base ou que nao existe), diga claramente: "Nao ha dados suficientes
   na base para responder."
3. Pode fazer multiplas consultas se necessario.
4. NAO use INSERT, UPDATE ou DELETE.
5. Ao responder, mostre o numero exato encontrado e mencione brevemente
   como chegou nele.

SCHEMA DO BANCO:
{_schema_cache}
"""


def _executar_chamada_de_ferramenta(bloco) -> str:
    """Executa o SQL pedido pela LLM e devolve resultado como texto."""
    sql = bloco.input.get("sql", "")
    try:
        rows, cols = executar_sql(sql)
        max_linhas = 50
        if len(rows) > max_linhas:
            preview = rows[:max_linhas]
            texto = (
                f"Colunas: {cols}\n"
                f"Linhas (mostrando {max_linhas} de {len(rows)}): {preview}"
            )
        else:
            texto = f"Colunas: {cols}\nLinhas ({len(rows)}): {rows}"
        return texto
    except Exception as e:
        return f"ERRO_SQL: {e}"


def responder(pergunta: str, max_iteracoes: int = 8) -> dict:
    """
    Loop ReAct: o modelo pode chamar `executar_sql` varias vezes
    antes de produzir a resposta final.
    """
    inicio = time.time()
    mensagens = [{"role": "user", "content": pergunta}]
    sqls_executados: list[str] = []
    tokens_in_total = 0
    tokens_out_total = 0
    erro = ""
    resposta_final = ""

    try:
        for _ in range(max_iteracoes):
            resp = _cliente.messages.create(
                model=MODELO_PADRAO,
                max_tokens=2048,
                system=_system_prompt(),
                tools=[FERRAMENTA_SQL],
                messages=mensagens,
            )
            tokens_in_total += resp.usage.input_tokens
            tokens_out_total += resp.usage.output_tokens

            if resp.stop_reason == "end_turn":
                resposta_final = "".join(
                    b.text for b in resp.content if hasattr(b, "text")
                )
                break

            if resp.stop_reason == "tool_use":
                mensagens.append({"role": "assistant", "content": resp.content})

                resultados_de_ferramenta = []
                for bloco in resp.content:
                    if bloco.type == "tool_use":
                        sql_pedido = bloco.input.get("sql", "")
                        sqls_executados.append(sql_pedido)
                        texto_resultado = _executar_chamada_de_ferramenta(bloco)
                        resultados_de_ferramenta.append({
                            "type": "tool_result",
                            "tool_use_id": bloco.id,
                            "content": texto_resultado,
                        })

                mensagens.append({"role": "user", "content": resultados_de_ferramenta})
                continue

            erro = f"stop_reason inesperado: {resp.stop_reason}"
            break
        else:
            erro = f"excedeu max_iteracoes ({max_iteracoes})"

    except Exception as e:
        erro = str(e)

    return {
        "pergunta": pergunta,
        "resposta": resposta_final,
        "tokens_input": tokens_in_total,
        "tokens_output": tokens_out_total,
        "latencia_s": round(time.time() - inicio, 2),
        "modelo": MODELO_PADRAO,
        "abordagem": "mcp",
        "iteracoes": len(sqls_executados),
        "sqls_executados": sqls_executados,
        "erro": erro,
    }


if __name__ == "__main__":
    print(f"Modelo: {MODELO_PADRAO}\n")
    pergunta = "Quantos pedidos existem na base e qual o range de datas?"
    print(f"Pergunta: {pergunta}\n")

    r = responder(pergunta)
    print(f"Resposta:\n{r['resposta']}\n")
    print(f"SQLs executados ({r['iteracoes']}):")
    for sql in r["sqls_executados"]:
        print(f"  - {sql}")
    print(f"\nLatencia: {r['latencia_s']}s")
    print(f"Tokens: {r['tokens_input']} input + {r['tokens_output']} output")
    if r["erro"]:
        print(f"ERRO: {r['erro']}")
