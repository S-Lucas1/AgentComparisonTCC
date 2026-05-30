"""
PROTOTIPO B - LLM COM ACESSO AO BANCO VIA MCP REAL
====================================================

A LLM tem acesso ao banco PostgreSQL via MCP (Model Context Protocol).
O protocolo JSON-RPC sobre stdio conecta um cliente Python (este arquivo)
a um servidor Node.js (@modelcontextprotocol/server-postgres) que expoe
a ferramenta `query` para executar SELECTs no banco.

Fluxo:
  1. Inicia o servidor MCP como subprocesso via npx.
  2. Conecta o cliente MCP Python via stdio (JSON-RPC).
  3. Lista as tools do servidor MCP e as converte para o formato Anthropic.
  4. Executa loop ReAct (max 8 iteracoes): quando o LLM faz tool_use,
     chama session.call_tool() via MCP em vez de executar SQL localmente.
  5. Retorna dict com os mesmos 12 campos do logger (interface identica ao
     Prototipo A, garantindo compatibilidade com o runner).
"""
import asyncio
import logging
import os
import sys
import time

import anthropic
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from src.config import ANTHROPIC_API_KEY, DB_CONFIG, MODELO_PADRAO
from src.db import obter_schema_resumido

logger = logging.getLogger(__name__)

_cliente = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_schema_cache: str | None = None


def _db_url() -> str:
    c = DB_CONFIG
    return (
        f"postgresql://{c['user']}:{c['password']}"
        f"@{c['host']}:{c['port']}/{c['dbname']}"
    )


def _mcp_server_params() -> StdioServerParameters:
    """
    Monta os parametros para iniciar o servidor MCP postgres como subprocesso.
    Adiciona o diretorio do Node.js ao PATH para garantir que npx funcione
    mesmo quando o terminal nao atualizou o PATH apos a instalacao.
    """
    env = dict(os.environ)
    nodejs_candidates = [
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
    ]
    for p in nodejs_candidates:
        if os.path.isdir(p) and p not in env.get("PATH", ""):
            env["PATH"] = p + os.pathsep + env.get("PATH", "")

    db_url = _db_url()

    # --prefer-offline: usa o pacote em cache e PULA a checagem de versao no
    # registry npm. Sem isso, cada spawn faz uma chamada de rede que pode
    # pendurar por dezenas de segundos (gargalo principal do Prototipo B).
    # Cai para a rede normalmente se o pacote ainda nao estiver em cache.
    if sys.platform == "win32":
        # No Windows, .cmd precisa de cmd.exe /c para ser executado
        command = "cmd.exe"
        args = ["/c", "npx", "--prefer-offline", "-y",
                "@modelcontextprotocol/server-postgres", db_url]
    else:
        command = "npx"
        args = ["--prefer-offline", "-y",
                "@modelcontextprotocol/server-postgres", db_url]

    return StdioServerParameters(command=command, args=args, env=env)


def _system_prompt() -> str:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = obter_schema_resumido()

    return f"""Voce e um analista de dados respondendo perguntas sobre uma base \
de e-commerce brasileira (Olist).

VOCE TEM ACESSO AO BANCO via a ferramenta `query`.

REGRAS IMPORTANTES:
1. SEMPRE busque dados reais via `query` antes de responder.
2. Se a pergunta nao puder ser respondida com os dados (ex: dado fora da
   base ou que nao existe), diga claramente: "Nao ha dados suficientes
   na base para responder."
3. Pode fazer multiplas consultas se necessario.
4. NAO use INSERT, UPDATE ou DELETE - a ferramenta e read-only.
5. Ao responder, mostre o numero exato encontrado e mencione brevemente
   como chegou nele.

SCHEMA DO BANCO:
{_schema_cache}
"""


def _tools_para_anthropic(tools) -> list[dict]:
    """Converte lista de tools MCP para o formato esperado pela API Anthropic."""
    result = []
    for t in tools:
        schema = t.inputSchema
        if not isinstance(schema, dict):
            schema = schema.model_dump()
        result.append({
            "name": t.name,
            "description": t.description or "",
            "input_schema": schema,
        })
    return result


async def _responder_async(pergunta: str, max_iteracoes: int = 8) -> dict:
    inicio = time.time()
    sqls_executados: list[str] = []
    tokens_in_total = 0
    tokens_out_total = 0
    erro = ""
    resposta_final = ""

    try:
        params = _mcp_server_params()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("MCP server iniciado")

                tools_mcp = (await session.list_tools()).tools
                tools_anthropic = _tools_para_anthropic(tools_mcp)

                mensagens = [{"role": "user", "content": pergunta}]

                for _ in range(max_iteracoes):
                    resp = _cliente.messages.create(
                        model=MODELO_PADRAO,
                        max_tokens=2048,
                        system=_system_prompt(),
                        tools=tools_anthropic,
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

                        resultados = []
                        for bloco in resp.content:
                            if bloco.type == "tool_use":
                                sql = bloco.input.get("sql", "")
                                sqls_executados.append(sql)
                                logger.info(f"MCP tool_call: {bloco.name}")

                                try:
                                    resultado_mcp = await session.call_tool(
                                        bloco.name, bloco.input
                                    )
                                    conteudo = "\n".join(
                                        c.text
                                        for c in resultado_mcp.content
                                        if hasattr(c, "text")
                                    )
                                except Exception as e:
                                    conteudo = f"ERRO_MCP: {e}"

                                resultados.append({
                                    "type": "tool_result",
                                    "tool_use_id": bloco.id,
                                    "content": conteudo,
                                })

                        mensagens.append({"role": "user", "content": resultados})
                        continue

                    erro = f"stop_reason inesperado: {resp.stop_reason}"
                    break
                else:
                    erro = f"excedeu max_iteracoes ({max_iteracoes})"

    except Exception as e:
        msg_erro = str(e)
        if "<html" in msg_erro.lower() or "proxy" in msg_erro.lower():
            erro = "PROXY_BLOCK: API interceptada por proxy corporativo. Verifique a rede."
        else:
            erro = msg_erro

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


def responder(pergunta: str, max_iteracoes: int = 8) -> dict:
    """
    Envia a pergunta ao LLM que usa MCP para consultar o PostgreSQL.
    Interface sync; internamente usa asyncio.run() para envolver o codigo async.
    """
    return asyncio.run(_responder_async(pergunta, max_iteracoes))


# Permite rodar este arquivo diretamente para teste:
#   python -m src.prototipo_b_mcp
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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
