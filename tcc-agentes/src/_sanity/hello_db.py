"""
Sanity check 2: o banco Olist esta acessivel e populado?

Uso:
    python -m src._sanity.hello_db
"""
from src.db import executar_sql, obter_estatisticas_resumidas


def main():
    print("Conectando no PostgreSQL...\n")

    rows, _ = executar_sql("SELECT COUNT(*) FROM orders;")
    total = rows[0][0]
    print(f"Total de pedidos: {total:,}")

    if total < 99000:
        print("\n[AVISO] Esperavam-se ~99.441 pedidos. A importacao esta completa?")
        return

    print("\n--- Estatisticas resumidas ---")
    print(obter_estatisticas_resumidas())

    print("\n[OK] Banco Olist esta acessivel e parece completo.")


if __name__ == "__main__":
    main()
