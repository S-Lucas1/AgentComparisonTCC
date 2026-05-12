"""
Utilitario de acesso ao banco PostgreSQL Olist.

Expoe duas funcoes principais:
  - executar_sql(sql)        -> retorna (linhas, nomes_de_colunas)
  - obter_schema_resumido()  -> retorna texto descrevendo as tabelas

Esses dois utilitarios sao usados pelos dois prototipos.
"""
from contextlib import contextmanager
import psycopg2
from src.config import DB_CONFIG


@contextmanager
def conectar():
    """Abre uma conexao e garante que ela seja fechada no final."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def executar_sql(sql: str, params: tuple | None = None) -> tuple[list, list[str]]:
    """
    Executa uma query SQL e retorna (linhas, nomes_de_colunas).
    Para queries sem retorno (ex: INSERT), retorna ([], []).

    Exemplo:
        rows, cols = executar_sql("SELECT customer_state, COUNT(*) FROM customers GROUP BY 1")
        # rows = [('SP', 41746), ('RJ', 12852), ...]
        # cols = ['customer_state', 'count']
    """
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is not None:
                colunas = [desc[0] for desc in cur.description]
                linhas = cur.fetchall()
                return linhas, colunas
            return [], []


def obter_schema_resumido() -> str:
    """
    Retorna uma representacao textual do schema (tabelas + colunas + tipos).
    Usado pelos prototipos para "informar" o LLM sobre a estrutura da base.
    """
    sql = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    rows, _ = executar_sql(sql)

    out_linhas = ["Schema da base Olist (PostgreSQL):", ""]
    tabela_atual = None
    for tabela, coluna, tipo in rows:
        if tabela != tabela_atual:
            out_linhas.append(f"\nTabela: {tabela}")
            tabela_atual = tabela
        out_linhas.append(f"  - {coluna} ({tipo})")

    return "\n".join(out_linhas)


def obter_estatisticas_resumidas() -> str:
    """
    Retorna estatisticas agregadas das principais tabelas.
    Essas estatisticas sao injetadas no prompt do Prototipo A
    para dar 'algum contexto' alem do schema puro.
    """
    queries = {
        "Total de pedidos": "SELECT COUNT(*) FROM orders;",
        "Total de clientes unicos": "SELECT COUNT(DISTINCT customer_unique_id) FROM customers;",
        "Total de produtos": "SELECT COUNT(*) FROM products;",
        "Total de vendedores": "SELECT COUNT(*) FROM sellers;",
        "Range de datas dos pedidos": (
            "SELECT MIN(order_purchase_timestamp)::date || ' a ' || "
            "MAX(order_purchase_timestamp)::date FROM orders;"
        ),
        "Estados com mais clientes (top 5)": (
            "SELECT customer_state || ': ' || COUNT(*) FROM customers "
            "GROUP BY customer_state ORDER BY COUNT(*) DESC LIMIT 5;"
        ),
        "Status dos pedidos": (
            "SELECT order_status || ': ' || COUNT(*) FROM orders "
            "GROUP BY order_status ORDER BY COUNT(*) DESC;"
        ),
    }

    linhas = ["Estatisticas resumidas da base:", ""]
    for nome, sql in queries.items():
        rows, _ = executar_sql(sql)
        if rows and len(rows) == 1 and len(rows[0]) == 1:
            linhas.append(f"- {nome}: {rows[0][0]}")
        else:
            valores = "; ".join(str(r[0]) for r in rows)
            linhas.append(f"- {nome}: {valores}")

    return "\n".join(linhas)
