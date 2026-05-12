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
from src.logger import salvar_resultado


def carregar_perguntas(caminho: str) -> list[dict]:
    """Le o CSV de perguntas. Espera coluna 'id' e 'pergunta'."""
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(caminho_csv: str = "data/perguntas_exemplo.csv"):
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
                    print(f"  {nome}: ERRO -> {r['erro']}")
                else:
                    print(
                        f"  {nome}: OK ({r['latencia_s']}s, "
                        f"{r['tokens_input']}+{r['tokens_output']} tok"
                        + (f", {r['iteracoes']} chamadas)" if r["iteracoes"] > 1 else ")")
                    )
            except Exception as e:
                print(f"  {nome}: EXCECAO -> {e}")

        print()

    print(f"Concluido. Resultados em resultados/")


if __name__ == "__main__":
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "data/perguntas_exemplo.csv"
    main(arquivo)
