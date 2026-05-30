"""
FRONTEND GRADIO PARA OS PROTOTIPOS DO TCC
==========================================

Duas abas:
  - Chat: pergunta unica, abordagem A, B ou ambos em paralelo (tabela comparativa).
  - Bateria CSV: upload de um CSV com perguntas, roda em batch, salva log e
    permite download do CSV de resultados.

Cada chamada e independente (sem memoria entre turnos), refletindo o
desenho experimental do TCC (Q -> A pontual).

Uso:
    python -m src.app_gradio
"""
import concurrent.futures
import csv
import html
import os

import gradio as gr

from src.config import MODELO_PADRAO
from src.logger import arquivo_de_log, iniciar_run, salvar_resultado
from src.prototipo_a_contexto import responder as responder_a
from src.prototipo_b_mcp import responder as responder_b


OPCAO_A = "Protótipo A — contexto puro"
OPCAO_B = "Protótipo B — MCP"
OPCAO_AMBOS = "Ambos (paralelo)"


# ============================================================
# Helpers de formatacao do CHAT
# ============================================================

def _rodape(r: dict) -> str:
    return (
        f"*`{r['modelo']}` · {r['latencia_s']}s · "
        f"{r['tokens_input']} tok in / {r['tokens_output']} tok out*"
    )


def _bloco_solo_a(r: dict) -> str:
    corpo = f"Erro: {r['erro']}" if r["erro"] else r["resposta"]
    return f"Opção A {OPCAO_A}\n\n{corpo}\n\n{_rodape(r)}"


def _bloco_solo_b(r: dict) -> str:
    if r["erro"]:
        return f"Opção B {OPCAO_B}\n\nErro: {r['erro']}\n\n{_rodape(r)}"
    partes = [f"Opção B {OPCAO_B}", "", r["resposta"]]
    if r.get("sqls_executados"):
        sqls_md = "\n".join(
            f"```sql\n{sql.strip()}\n```" for sql in r["sqls_executados"]
        )
        partes += ["", f"**SQLs executados ({len(r['sqls_executados'])}):**", sqls_md]
    partes += ["", _rodape(r)]
    return "\n".join(partes)


def _cell(s: str) -> str:
    """Escapa conteudo para celula de tabela markdown."""
    if not s:
        return "—"
    return s.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _tabela_comparacao(r_a: dict, r_b: dict) -> str:
    """Tabela markdown comparando A e B lado a lado."""
    resp_a = _cell(f"{r_a['erro']}" if r_a["erro"] else r_a["resposta"])
    resp_b = _cell(f"{r_b['erro']}" if r_b["erro"] else r_b["resposta"])

    if r_b.get("sqls_executados"):
        # <code> e inline (cabe na celula). <br> preserva as quebras de linha.
        # <pre> seria melhor para indentacao, mas e bloco e quebra o layout
        # da tabela no renderizador do Gradio.
        sqls_html = "<br><br>".join(
            f"<code>{html.escape(sql.strip()).replace(chr(10), '<br>')}</code>"
            for sql in r_b["sqls_executados"]
        )
    else:
        sqls_html = "—"

    linhas = [
        "| | Protótipo A (contexto) | Protótipo B (MCP) |",
        "|---|---|---|",
        f"| **Resposta** | {resp_a} | {resp_b} |",
        f"| **Latência** | {r_a['latencia_s']}s | {r_b['latencia_s']}s |",
        f"| **Tokens input** | {r_a['tokens_input']} | {r_b['tokens_input']} |",
        f"| **Tokens output** | {r_a['tokens_output']} | {r_b['tokens_output']} |",
        f"| **Iterações (tool calls)** | {r_a['iteracoes']} | {r_b['iteracoes']} |",
        f"| **SQL executado** | — | {sqls_html} |",
        f"| **Modelo** | `{r_a['modelo']}` | `{r_b['modelo']}` |",
    ]
    return "\n".join(linhas)


def chat(pergunta: str, historico: list, abordagem: str) -> str:
    if abordagem == OPCAO_A:
        return _bloco_solo_a(responder_a(pergunta))

    if abordagem == OPCAO_B:
        return _bloco_solo_b(responder_b(pergunta))

    # Ambos em paralelo: tempo total = max(t_A, t_B), nao soma.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(responder_a, pergunta)
        fut_b = pool.submit(responder_b, pergunta)
        r_a = fut_a.result()
        r_b = fut_b.result()

    return _tabela_comparacao(r_a, r_b)


# ============================================================
# BATERIA CSV
# ============================================================

def _ler_perguntas_csv(caminho: str) -> list[dict]:
    with open(caminho, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _linha_resultado(pid: str, nome: str, pergunta: str, r: dict, erro: str) -> dict:
    """Linha resumida para exibir na tabela de progresso (markdown)."""
    resposta = (r.get("resposta") or "").replace("\n", " ")
    return {
        "id": pid,
        "abordagem": nome,
        "pergunta": pergunta[:80],
        "resposta": resposta[:120],
        "latencia_s": r.get("latencia_s", ""),
        "tok_in": r.get("tokens_input", 0),
        "tok_out": r.get("tokens_output", 0),
        "iter": r.get("iteracoes", 0),
        "erro": (erro or "")[:80],
    }


def _md_tabela_resultados(resultados: list[dict]) -> str:
    """Renderiza a lista de resultados como tabela markdown."""
    if not resultados:
        return "_Sem resultados ainda._"

    def _e(s):
        if s is None or s == "":
            return ""
        return str(s).replace("|", "\\|").replace("\n", " ")

    md = [
        "| id | abordagem | pergunta | resposta | lat (s) | tok in/out | iter | erro |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        md.append(
            f"| {_e(r['id'])} | {_e(r['abordagem'])} | {_e(r['pergunta'])} "
            f"| {_e(r['resposta'])} | {_e(r['latencia_s'])} "
            f"| {_e(r['tok_in'])}/{_e(r['tok_out'])} | {_e(r['iter'])} "
            f"| {_e(r['erro'])} |"
        )
    return "\n".join(md)


def _executar_e_logar(pid: str, pergunta: str, nome: str, fn) -> tuple[dict, str]:
    """Roda uma abordagem, salva no log do dia, retorna (resultado, erro)."""
    try:
        r = fn(pergunta)
        r["id_pergunta"] = pid
        salvar_resultado(r)
        return r, r.get("erro", "")
    except Exception as e:
        r_erro = {
            "resposta": "",
            "tokens_input": 0,
            "tokens_output": 0,
            "latencia_s": 0,
            "iteracoes": 0,
            "modelo": MODELO_PADRAO,
            "abordagem": nome,
            "sqls_executados": [],
            "erro": str(e),
            "pergunta": pergunta,
            "id_pergunta": pid,
        }
        try:
            salvar_resultado(r_erro)
        except Exception:
            pass
        return r_erro, str(e)


def rodar_bateria(arquivo, abordagem: str):
    """
    Generator que processa cada pergunta do CSV e vai dando yield com
    (progresso_markdown, dataframe_parcial, caminho_do_log_para_download).
    """
    if not arquivo:
        yield "Caminho do CSV vazio.", _md_tabela_resultados([]), None
        return

    caminho = arquivo if isinstance(arquivo, str) else arquivo.name

    if not os.path.isfile(caminho):
        yield f"Arquivo não encontrado: `{caminho}` (cwd: `{os.getcwd()}`)", _md_tabela_resultados([]), None
        return

    try:
        perguntas = _ler_perguntas_csv(caminho)
    except Exception as e:
        yield f"Erro lendo CSV: `{e}`", _md_tabela_resultados([]), None
        return

    if not perguntas:
        yield "CSV vazio.", _md_tabela_resultados([]), None
        return

    if "pergunta" not in perguntas[0]:
        cols = list(perguntas[0].keys())
        yield (
            f"CSV precisa de uma coluna chamada `pergunta`. Colunas encontradas: `{cols}`",
            _md_tabela_resultados([]),
            None,
        )
        return

    abordagens = []
    if abordagem in (OPCAO_A, OPCAO_AMBOS):
        abordagens.append(("A_contexto", responder_a))
    if abordagem in (OPCAO_B, OPCAO_AMBOS):
        abordagens.append(("B_mcp", responder_b))

    iniciar_run()
    log_path = str(arquivo_de_log())

    resultados: list[dict] = []
    total = len(perguntas) * len(abordagens)
    feito = 0

    # Yields que enviam o log_path para o componente de download so podem
    # acontecer DEPOIS de salvar_resultado() ter criado o arquivo. Antes
    # disso, mandamos None para evitar FileNotFoundError no gr.File.
    def _download_atual() -> str | None:
        return log_path if os.path.isfile(log_path) else None

    yield (
        f"Iniciando: {len(perguntas)} perguntas x {len(abordagens)} abordagem(ns) = {total} chamadas.\n\n"
        f"Log: `{log_path}`",
        _md_tabela_resultados([]),
        _download_atual(),
    )

    for i, p in enumerate(perguntas, 1):
        pid = p.get("id") or f"P{i:03d}"
        pergunta = p.get("pergunta", "").strip()
        if not pergunta:
            continue

        if abordagem == OPCAO_AMBOS:
            # A e B em paralelo por pergunta (cai de soma para max).
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                fut_a = pool.submit(_executar_e_logar, pid, pergunta, "A_contexto", responder_a)
                fut_b = pool.submit(_executar_e_logar, pid, pergunta, "B_mcp", responder_b)
                r_a, erro_a = fut_a.result()
                r_b, erro_b = fut_b.result()
            resultados.append(_linha_resultado(pid, "A_contexto", pergunta, r_a, erro_a))
            resultados.append(_linha_resultado(pid, "B_mcp", pergunta, r_b, erro_b))
            feito += 2
        else:
            nome, fn = abordagens[0]
            r, erro = _executar_e_logar(pid, pergunta, nome, fn)
            resultados.append(_linha_resultado(pid, nome, pergunta, r, erro))
            feito += 1

        progresso = (
            f"**Progresso:** {feito}/{total} "
            f"({100 * feito // total}%) — última: `{pid}`"
        )
        yield progresso, _md_tabela_resultados(resultados), _download_atual()

    yield (
        f"**Concluído:** {feito}/{total} chamadas. "
        f"Log final: `{log_path}` (clique abaixo para baixar)",
        _md_tabela_resultados(resultados),
        _download_atual(),
    )


# ============================================================
# UI
# ============================================================

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="TCC - Comparação de agentes", fill_height=True) as demo:
        gr.Markdown(
            f"# TCC - Comparação de agentes\n"
            f"Modelo atual: `{MODELO_PADRAO}`."
        )

        gr.Markdown("Cada mensagem é uma chamada independente (sem memória entre turnos).")
        seletor = gr.Radio(
            choices=[OPCAO_A, OPCAO_B, OPCAO_AMBOS],
            value=OPCAO_A,
            label="Abordagem",
            info="'Ambos' dispara A e B em paralelo e mostra os resultados em tabela comparativa.",
        )
        gr.ChatInterface(
            fn=chat,
            additional_inputs=[seletor],
            examples=[
                ["Quantos pedidos existem na base?", OPCAO_A],
                ["Qual estado tem mais clientes cadastrados?", OPCAO_B],
                ["Qual o ticket médio dos pedidos 'delivered' em 2017?", OPCAO_AMBOS],
                ["Qual o faturamento total da empresa em janeiro de 2025?", OPCAO_AMBOS],
            ],
        )

        with gr.Accordion("Bateria CSV (rodar perguntas em batch)", open=False):
            gr.Markdown(
                "Upload de um CSV com colunas `id` e `pergunta`. "
                "Resultados são gravados em `resultados/resultados_*.csv` e ficam "
                "disponíveis para download abaixo após a execução."
            )

            arquivo_csv = gr.File(
                label="CSV de perguntas",
                file_types=[".csv"],
                type="filepath",
            )
            abordagem_batch = gr.Radio(
                choices=[OPCAO_A, OPCAO_B, OPCAO_AMBOS],
                value=OPCAO_AMBOS,
                label="Abordagem",
            )

            btn_rodar = gr.Button("Rodar bateria", variant="primary")

            progresso_md = gr.Markdown("Pronto para rodar.")
            tabela = gr.Markdown("_Sem resultados ainda._")
            download = gr.File(label="CSV de log para download")

            btn_rodar.click(
                fn=rodar_bateria,
                inputs=[arquivo_csv, abordagem_batch],
                outputs=[progresso_md, tabela, download],
            )

    return demo


if __name__ == "__main__":
    build_ui().launch()
