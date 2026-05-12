"""
Sanity check 1: API da Anthropic esta acessivel?

Se isto rodar sem erro e imprimir uma resposta, sua chave de API esta OK.

Uso:
    python -m src._sanity.hello_claude
"""
from anthropic import Anthropic
from src.config import ANTHROPIC_API_KEY, MODELO_PADRAO


def main():
    cliente = Anthropic(api_key=ANTHROPIC_API_KEY)

    print(f"Modelo: {MODELO_PADRAO}")
    print("Enviando 'oi' para a API...\n")

    msg = cliente.messages.create(
        model=MODELO_PADRAO,
        max_tokens=100,
        messages=[{"role": "user", "content": "Diga 'API funcionando!' em portugues."}],
    )

    print(f"Resposta: {msg.content[0].text}")
    print(f"\nTokens: {msg.usage.input_tokens} input + {msg.usage.output_tokens} output")
    print("\n[OK] API da Anthropic esta funcional.")


if __name__ == "__main__":
    main()
