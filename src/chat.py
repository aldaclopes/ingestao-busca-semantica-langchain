import os
import sys

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

sys.path.insert(0, os.path.dirname(__file__))
from ingest import ingest_pdf
from search import search_similar_chunks

load_dotenv()

LLM_MODEL = os.environ["GOOGLE_LLM_MODEL"]

PROMPT_TEMPLATE = """CONTEXTO:
{contexto}

REGRAS:
- Responda somente com base no CONTEXTO.
- Se a informação não estiver explicitamente no CONTEXTO, responda:
  "Não tenho informações necessárias para responder sua pergunta."
- Nunca invente ou use conhecimento externo.
- Nunca produza opiniões ou interpretações além do que está escrito.

EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO:
Pergunta: "Qual é a capital da França?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Quantos clientes temos em 2024?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Você acha isso bom ou ruim?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

PERGUNTA DO USUÁRIO:
{pergunta}

RESPONDA A "PERGUNTA DO USUÁRIO"
"""


def build_prompt(pergunta, resultados):
    contexto = "\n\n".join(doc.page_content for doc, _score in resultados)
    return PROMPT_TEMPLATE.format(contexto=contexto, pergunta=pergunta)


def answer_question(pergunta):
    resultados = search_similar_chunks(pergunta, k=10)
    prompt = build_prompt(pergunta, resultados)
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL)
    resposta = llm.invoke(prompt)
    return resposta.content


def main():
    print("Faça sua pergunta (ou 'sair' para encerrar).")
    print("Comando especial: anexar <caminho_do_pdf> — ingere um novo PDF no banco para consultas futuras.\n")

    while True:
        entrada = input("PERGUNTA: ").strip()
        if not entrada:
            continue
        if entrada.lower() in ("sair", "exit", "quit"):
            break

        if entrada.lower().startswith("anexar "):
            pdf_path = os.path.expanduser(entrada[len("anexar "):].strip().strip('"').strip("'"))
            if not os.path.isfile(pdf_path):
                print(f"Arquivo não encontrado: {pdf_path}\n")
                continue
            print(f"Lendo e indexando '{pdf_path}'...")
            n_chunks = ingest_pdf(pdf_path)
            print(f"Pronto: {n_chunks} chunks adicionados ao banco. Já pode perguntar sobre ele.\n")
            continue

        resposta = answer_question(entrada)
        print(f"RESPOSTA: {resposta}\n")


if __name__ == "__main__":
    main()
