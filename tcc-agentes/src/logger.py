"""
Sistema simples de logging dos experimentos.

Cada execucao de uma pergunta gera uma linha num CSV em resultados/.
Um CSV por dia para facilitar revisao posterior.
"""
import csv
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "resultados"
LOG_DIR.mkdir(exist_ok=True)

CAMPOS = [
    "timestamp",
    "id_pergunta",
    "abordagem",       # "contexto" (Prototipo A) ou "mcp" (Prototipo B)
    "modelo",
    "pergunta",
    "resposta",
    "tokens_input",
    "tokens_output",
    "latencia_s",
    "iteracoes",       # quantas vezes o LLM chamou ferramenta (so faz sentido pro B)
    "sqls_executados", # SQLs gerados pelo LLM (so para o B), separados por |
    "erro",            # mensagem de erro, se houver
]


_run_ts: str | None = None


def iniciar_run() -> None:
    """Fixa o timestamp da run. Chamar uma vez antes de salvar resultados."""
    global _run_ts
    _run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M")


def arquivo_de_log() -> Path:
    """Um arquivo por run. Se iniciar_run() nao foi chamado, usa o momento atual."""
    ts = _run_ts or datetime.now().strftime("%Y-%m-%d_%H-%M")
    return LOG_DIR / f"resultados_{ts}.csv"


def _limpar_erro(msg: str) -> str:
    """Remove newlines, colapsa espaços e trunca a 300 chars."""
    sem_tags = re.sub(r"<[^>]+>", "", msg)      # strip HTML tags se houver
    colapsado = re.sub(r"\s+", " ", sem_tags).strip()
    return colapsado[:300]


def salvar_resultado(r: dict) -> None:
    """
    Anexa uma linha ao CSV do dia.
    Espera um dict com as chaves do CAMPOS (faltantes viram vazio).
    """
    arq = arquivo_de_log()
    eh_arquivo_novo = not arq.exists()

    linha = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "id_pergunta": r.get("id_pergunta", ""),
        "abordagem": r.get("abordagem", ""),
        "modelo": r.get("modelo", ""),
        "pergunta": r.get("pergunta", ""),
        "resposta": r.get("resposta", ""),
        "tokens_input": r.get("tokens_input", 0),
        "tokens_output": r.get("tokens_output", 0),
        "latencia_s": r.get("latencia_s", 0),
        "iteracoes": r.get("iteracoes", 1),
        "sqls_executados": " | ".join(
            re.sub(r"\s+", " ", sql).strip()
            for sql in (r.get("sqls_executados", []) or [])
        ),
        "erro": _limpar_erro(str(r.get("erro", ""))),
    }

    with open(arq, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        if eh_arquivo_novo:
            writer.writeheader()
        writer.writerow(linha)
