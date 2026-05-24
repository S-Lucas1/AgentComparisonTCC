"""
RUNNER DOS EXPERIMENTOS
========================

Le um CSV de perguntas, executa cada uma nos dois prototipos
e salva os resultados via logger.

Uso:
    python -m src.runner
    python -m src.runner data/outro_arquivo.csv
"""
import csv
import sys
from pathlib import Path

from src.prototipo_a_contexto import responder as responder_a
from src.prototipo_b_mcp import responder as responder_b
from src.logger import salvar_resultado, iniciar_run

_ROOT = Path(__file__).resolve().parent.parent


def carregar_perguntas(caminho: str) -> list[dict]:
    """Le o CSV de perguntas. Espera coluna 'id' e 'pergunta'."""
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(caminho_csv: str | None = None):
    if caminho_csv is None:
        caminho_csv = str(_ROOT / "data" / "perguntas_50_oficiais_final.csv")
    iniciar_run()
    perguntas = carregar_perguntas(caminho_csv)
    print(f"Carregadas {len(perguntas)} perguntas de {caminho_csv}\n")

    abordagens = [
        ("A_contexto", responder_a),
        ("B_mcp", responder_b),
    ]

    for i, p in enumerate(perguntas, 1):
        pid = p.get("id") or f"P{i:03d}"
        pergunta = p["pergunta"]
        print(f"[{i}/{len(perguntas)}] {pid}: {pergunta[:70]}")

        for nome, fn in abordagens:
            try:
                r = fn(pergunta)
                r["id_pergunta"] = pid
                salvar_resultado(r)
                if r["erro"]:
                    resumo_erro = str(r["erro"])[:120].encode(
                        sys.stdout.encoding or "utf-8", errors="replace"
                    ).decode(sys.stdout.encoding or "utf-8", errors="replace")
                    print(f"  {nome}: ERRO -> {resumo_erro}")
                else:
                    meta = (
                        f"{r['latencia_s']}s, "
                        f"{r['tokens_input']}+{r['tokens_output']} tok"
                        + (f", {r['iteracoes']} iter" if r["iteracoes"] > 1 else "")
                    )
                    resposta_curta = r["resposta"].replace("\n", " ")[:120]
                    print(f"  {nome} ({meta}): {resposta_curta}")
            except Exception as e:
                resumo = str(e)[:120].encode(
                    sys.stdout.encoding or "utf-8", errors="replace"
                ).decode(sys.stdout.encoding or "utf-8", errors="replace")
                print(f"  {nome}: EXCECAO -> {resumo}")

        print()

    from src.logger import LOG_DIR
    print(f"Concluido. Resultados em {LOG_DIR}")


if __name__ == "__main__":
    arquivo = sys.argv[1] if len(sys.argv) > 1 else None
    main(arquivo)
