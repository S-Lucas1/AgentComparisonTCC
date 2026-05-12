"""
Configuracao central do projeto.

Carrega variaveis do arquivo .env e expoe como constantes.
Qualquer modulo que precisar dessas configuracoes importa daqui.
"""
import os
from dotenv import load_dotenv

# Carrega variaveis do arquivo .env (precisa estar na raiz do projeto)
load_dotenv()

# === API da Anthropic ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY nao encontrada. "
        "Copie .env.example para .env e preencha sua chave."
    )

# === Banco de dados ===
DB_CONFIG = {
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "olist"),
}

# === Modelo LLM padrao ===
# Trocar aqui para rodar com modelo diferente.
# Lista oficial: https://docs.claude.com/en/docs/about-claude/models
MODELO_PADRAO = os.getenv("MODELO_PADRAO", "claude-haiku-4-5")
