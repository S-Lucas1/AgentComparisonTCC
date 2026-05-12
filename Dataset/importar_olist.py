"""
importar_olist.py
-----------------
Cria o schema e importa o dataset Olist Brazilian E-Commerce no PostgreSQL.

Uso:
    1. Edite as constantes de conexao abaixo (principalmente DB_PASS).
    2. Garanta que a pasta DATA_DIR contem os 9 arquivos CSV do Olist.
    3. Rode: python importar_olist.py

Tempo esperado: 2-5 minutos dependendo da maquina.
"""

import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

# =========================================================
# CONFIGURACAO - EDITE AQUI
# =========================================================
DB_USER = "postgres"
DB_PASS = "SenhaTCC123"   # senha definida na instalacao do PostgreSQL
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "olist"
DATA_DIR = "./olist_data"            # pasta com os CSVs descompactados


# =========================================================
# SCHEMA SQL - tabelas, FKs e indices
# =========================================================
SCHEMA_SQL = """
DROP TABLE IF EXISTS order_reviews, order_payments, order_items, orders,
                     products, sellers, customers, geolocation,
                     product_category_translation CASCADE;

CREATE TABLE customers (
    customer_id              VARCHAR PRIMARY KEY,
    customer_unique_id       VARCHAR,
    customer_zip_code_prefix VARCHAR,
    customer_city            VARCHAR,
    customer_state           VARCHAR
);

CREATE TABLE geolocation (
    geolocation_zip_code_prefix VARCHAR,
    geolocation_lat             DOUBLE PRECISION,
    geolocation_lng             DOUBLE PRECISION,
    geolocation_city            VARCHAR,
    geolocation_state           VARCHAR
);

CREATE TABLE sellers (
    seller_id              VARCHAR PRIMARY KEY,
    seller_zip_code_prefix VARCHAR,
    seller_city            VARCHAR,
    seller_state           VARCHAR
);

CREATE TABLE product_category_translation (
    product_category_name         VARCHAR PRIMARY KEY,
    product_category_name_english VARCHAR
);

CREATE TABLE products (
    product_id                 VARCHAR PRIMARY KEY,
    product_category_name      VARCHAR,
    product_name_lenght        INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           INTEGER,
    product_length_cm          INTEGER,
    product_height_cm          INTEGER,
    product_width_cm           INTEGER
);

CREATE TABLE orders (
    order_id                       VARCHAR PRIMARY KEY,
    customer_id                    VARCHAR REFERENCES customers(customer_id),
    order_status                   VARCHAR,
    order_purchase_timestamp       TIMESTAMP,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP
);

CREATE TABLE order_items (
    order_id            VARCHAR REFERENCES orders(order_id),
    order_item_id       INTEGER,
    product_id          VARCHAR REFERENCES products(product_id),
    seller_id           VARCHAR REFERENCES sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(10,2),
    freight_value       NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE order_payments (
    order_id             VARCHAR REFERENCES orders(order_id),
    payment_sequential   INTEGER,
    payment_type         VARCHAR,
    payment_installments INTEGER,
    payment_value        NUMERIC(10,2),
    PRIMARY KEY (order_id, payment_sequential)
);

-- Sem PK porque a base original tem review_ids duplicados (problema conhecido do dataset)
CREATE TABLE order_reviews (
    review_id              VARCHAR,
    order_id               VARCHAR REFERENCES orders(order_id),
    review_score           INTEGER,
    review_comment_title   TEXT,
    review_comment_message TEXT,
    review_creation_date   TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

CREATE INDEX idx_orders_customer    ON orders(customer_id);
CREATE INDEX idx_orders_status      ON orders(order_status);
CREATE INDEX idx_orders_purchase    ON orders(order_purchase_timestamp);
CREATE INDEX idx_order_items_prod   ON order_items(product_id);
CREATE INDEX idx_order_items_seller ON order_items(seller_id);
CREATE INDEX idx_payments_order     ON order_payments(order_id);
CREATE INDEX idx_reviews_order      ON order_reviews(order_id);
"""


# =========================================================
# Mapeamento CSV -> tabela, na ordem correta de carga
# (pais antes de filhos para respeitar as FKs)
# =========================================================
LOAD_ORDER = [
    ("olist_customers_dataset.csv",            "customers"),
    ("olist_geolocation_dataset.csv",          "geolocation"),
    ("olist_sellers_dataset.csv",              "sellers"),
    ("product_category_name_translation.csv",  "product_category_translation"),
    ("olist_products_dataset.csv",             "products"),
    ("olist_orders_dataset.csv",               "orders"),
    ("olist_order_items_dataset.csv",          "order_items"),
    ("olist_order_payments_dataset.csv",       "order_payments"),
    ("olist_order_reviews_dataset.csv",        "order_reviews"),
]


def main():
    # Conexao
    url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"ERRO ao conectar no PostgreSQL: {e}")
        print("Verifique DB_PASS, DB_HOST e se o servico do PostgreSQL esta rodando.")
        sys.exit(1)

    # Verifica se os CSVs existem
    if not os.path.isdir(DATA_DIR):
        print(f"ERRO: pasta '{DATA_DIR}' nao encontrada.")
        print("Descompacte o ZIP do Olist nessa pasta antes de rodar.")
        sys.exit(1)

    missing = [f for f, _ in LOAD_ORDER if not os.path.isfile(os.path.join(DATA_DIR, f))]
    if missing:
        print("ERRO: CSVs faltando em", DATA_DIR)
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)

    # Cria o schema
    print("Criando schema...")
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
    print("  OK\n")

    # Importa os CSVs na ordem correta
    for filename, table in LOAD_ORDER:
        path = os.path.join(DATA_DIR, filename)
        print(f"Importando {filename} -> {table}")
        df = pd.read_csv(path)

        # Converte colunas de timestamp para datetime se existirem
        for col in df.columns:
            if "timestamp" in col or "date" in col or col == "order_approved_at":
                df[col] = pd.to_datetime(df[col], errors="coerce")

        df.to_sql(
            table,
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )
        print(f"  {len(df):,} linhas inseridas\n")

    # Verificacao final
    print("=" * 50)
    print("VERIFICACAO - contagem de linhas por tabela:")
    print("=" * 50)
    with engine.connect() as conn:
        for _, table in LOAD_ORDER:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:.<40} {count:>10,}")

    # Query exemplo para confirmar que joins funcionam
    print("\nQuery de teste (top 5 estados por faturamento):")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT c.customer_state,
                   ROUND(SUM(oi.price)::numeric, 2) AS faturamento
            FROM orders o
            JOIN customers c   ON o.customer_id = c.customer_id
            JOIN order_items oi ON o.order_id    = oi.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_state
            ORDER BY faturamento DESC
            LIMIT 5;
        """)).fetchall()
        for row in rows:
            print(f"  {row[0]}: R$ {row[1]:,}")

    print("\nImportacao concluida com sucesso.")


if __name__ == "__main__":
    main()
