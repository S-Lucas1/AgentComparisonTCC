"""
PROTOTIPO A - LLM COM CONTEXTO PURO
====================================

A LLM recebe no prompt uma representacao TEXTUAL da base
(schema + estatisticas resumidas) e responde perguntas
SEM acessar o banco diretamente.

Esta e a abordagem que o TCC quer mostrar como insuficiente:
para perguntas que dependem de calculos sobre os dados,
o modelo so pode adivinhar, estimar ou alucinar.

NOTA METODOLOGICA: A 'representacao textual' aqui e um placeholder
inicial. A versao final do TCC pode incluir:
  - amostras das tabelas (head N)
  - sumarios estatisticos por categoria
  - dumps em CSV ate o limite do contexto
A escolha exata e parte do desenho experimental e deve ser
documentada no Capitulo 3 (Materiais e Metodos).
"""
import time
from anthropic import Anthropic

from src.config import ANTHROPIC_API_KEY, MODELO_PADRAO
from src.db import obter_schema_resumido, obter_estatisticas_resumidas


# Cliente da API. Reusado entre chamadas.
_cliente = Anthropic(api_key=ANTHROPIC_API_KEY)

# O contexto e gerado UMA VEZ na primeira chamada e cacheado.
_contexto_cache: str | None = None


def _construir_contexto() -> str:
    """Monta a representacao textual da base que vai no system prompt."""
    schema = obter_schema_resumido()
    stats = obter_estatisticas_resumidas()
    return f"{schema}\n\n{stats}"


def _system_prompt() -> str:
    global _contexto_cache
    if _contexto_cache is None:
        _contexto_cache = _construir_contexto()

    return f"""Voce e um analista de dados respondendo perguntas sobre uma base \
de e-commerce brasileira (Olist).

REGRAS IMPORTANTES:
1. Voce so tem acesso ao CONTEXTO abaixo. Nao tente acessar nenhum banco.
2. Se a informacao necessaria NAO estiver no contexto, diga claramente:
   "Nao ha dados suficientes no contexto para responder com precisao."
3. NAO invente numeros, datas ou estatisticas. Nao chute.
4. Quando responder, justifique brevemente onde no contexto encontrou a informacao.

CONTEXTO DA BASE:
{_contexto_cache}
"""


def responder(pergunta: str) -> dict:
    """
    Envia a pergunta ao LLM com o contexto pre-fabricado.
    Retorna dict com resposta e metadados experimentais.
    """
    inicio = time.time()
    erro = ""

    try:
        msg = _cliente.messages.create(
            model=MODELO_PADRAO,
            max_tokens=1024,
            system=_system_prompt(),
            messages=[{"role": "user", "content": pergunta}],
        )
        # Extrai o texto da resposta (pode ter mais de um bloco)
        resposta_texto = "".join(
            bloco.text for bloco in msg.content if hasattr(bloco, "text")
        )
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
    except Exception as e:
        resposta_texto = ""
        tokens_in = 0
        tokens_out = 0
        erro = str(e)

    return {
        "pergunta": pergunta,
        "resposta": resposta_texto,
        "tokens_input": tokens_in,
        "tokens_output": tokens_out,
        "latencia_s": round(time.time() - inicio, 2),
        "modelo": MODELO_PADRAO,
        "abordagem": "contexto",
        "iteracoes": 1,
        "sqls_executados": [],
        "erro": erro,
    }


# Permite rodar este arquivo diretamente para teste rapido:
#   python -m src.prototipo_a_contexto
if __name__ == "__main__":
    print(f"Modelo: {MODELO_PADRAO}\n")
    pergunta = "Quantos pedidos existem na base e qual o range de datas?"
    print(f"Pergunta: {pergunta}\n")

    r = responder(pergunta)
    print(f"Resposta:\n{r['resposta']}\n")
    print(f"Latencia: {r['latencia_s']}s")
    print(f"Tokens: {r['tokens_input']} input + {r['tokens_output']} output")
