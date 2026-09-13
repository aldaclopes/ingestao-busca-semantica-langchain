"""
Teste automatizado de ponta a ponta do fluxo de ingestão + busca + chat.

ATENÇÃO: este script reseta o banco (docker compose down -v / up -d) para
garantir um ponto de partida determinístico, e o deixa de volta só com
document.pdf ao final (mesmo se algum teste falhar no meio do caminho).
Rode com o Docker já instalado e o projeto configurado (.env preenchido).

Uso:
    source venv/bin/activate
    python tests/run_tests.py
"""
import datetime
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from ingest import ingest_pdf  # noqa: E402
from search import search_similar_chunks  # noqa: E402
from chat import answer_question  # noqa: E402

REFUSAL = "Não tenho informações necessárias para responder sua pergunta."
COMPOSE_FILE = os.path.join(ROOT, "docker-compose.yml")

EVIDENCE_DIR = os.path.join(ROOT, "tests", "evidencias")
os.makedirs(EVIDENCE_DIR, exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
EVIDENCE_PATH = os.path.join(EVIDENCE_DIR, f"evidencia_{timestamp}.txt")

lines = []
results = []


def log(text=""):
    print(text)
    lines.append(str(text))


def section(title):
    log()
    log("=" * 70)
    log(title)
    log("=" * 70)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def docker_logs(tail=15):
    r = run(["docker", "logs", "--tail", str(tail), "mba_ia_postgres"])
    return (r.stdout + r.stderr).strip()


def sql(query):
    r = run(["docker", "exec", "mba_ia_postgres", "psql", "-U", "postgres", "-d", "rag", "-c", query])
    if r.returncode != 0:
        return f"ERRO ao rodar query: {r.stderr.strip()}"
    return r.stdout.strip()


def sql_scalar(query):
    r = run(["docker", "exec", "mba_ia_postgres", "psql", "-U", "postgres", "-d", "rag", "-t", "-A", "-c", query])
    return r.stdout.strip()


def check(nome, condicao, detalhe=""):
    status = "PASS" if condicao else "FAIL"
    results.append((nome, status, detalhe))
    log(f"[{status}] {nome}" + (f" — {detalhe}" if detalhe else ""))
    return condicao


def ask_seguro(pergunta):
    """Chama answer_question protegendo o script de erros da API (ex: cota excedida)."""
    try:
        return answer_question(pergunta), None
    except Exception as exc:  # noqa: BLE001
        motivo = str(exc).splitlines()[0]
        if "RESOURCE_EXHAUSTED" in str(exc) or "quota" in str(exc).lower():
            motivo = "Cota gratuita da API excedida (limite diário do modelo). Tente novamente mais tarde ou troque GOOGLE_LLM_MODEL."
        return None, motivo


def reset_db():
    run(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"])
    r = run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"])
    time.sleep(4)
    return r


def main():
    pdf_path = os.path.join(ROOT, "document.pdf")
    fixtures_dir = os.path.join(ROOT, "tests", "fixtures")
    segundo_pdf = os.path.join(fixtures_dir, "segundo_documento_teste.pdf")

    section("0. Preparando ambiente (reset do banco para teste determinístico)")
    log("$ docker compose down -v && docker compose up -d")
    r = reset_db()
    log(r.stdout + r.stderr)
    log(docker_logs())

    section("1. Ingestão inicial do document.pdf")
    n1 = ingest_pdf(pdf_path)
    log(f">>> ingest_pdf('{pdf_path}') retornou: {n1} chunks")

    log("\n--- Log do container do banco (docker logs --tail 15) ---")
    log(docker_logs())

    log("\n--- Query de quantidade (total) ---")
    log(sql("SELECT count(*) FROM langchain_pg_embedding;"))

    log("\n--- Query de quantidade por arquivo de origem ---")
    log(sql("SELECT cmetadata->>'source' AS arquivo, count(*) FROM langchain_pg_embedding GROUP BY 1 ORDER BY 1;"))

    total_1 = int(sql_scalar("SELECT count(*) FROM langchain_pg_embedding;"))
    check("Contagem no banco bate com o retorno de ingest_pdf()", total_1 == n1, f"banco={total_1}, retorno={n1}")

    section("2. Pergunta DENTRO do contexto")
    pergunta1 = "Qual o objetivo desta resolução?"
    resposta1, erro1 = ask_seguro(pergunta1)
    log(f"PERGUNTA: {pergunta1}")
    if erro1:
        log(f"ERRO: {erro1}")
        results.append(("Pergunta dentro do contexto respondida", "ERROR", erro1))
    else:
        log(f"RESPOSTA: {resposta1}")
        check("Resposta dentro do contexto não é a recusa padrão", resposta1.strip() != REFUSAL)

    section("3. Pergunta FORA do contexto")
    pergunta2 = "Qual a capital da França?"
    resposta2, erro2 = ask_seguro(pergunta2)
    log(f"PERGUNTA: {pergunta2}")
    if erro2:
        log(f"ERRO: {erro2}")
        results.append(("Pergunta fora do contexto recusada corretamente", "ERROR", erro2))
    else:
        log(f"RESPOSTA: {resposta2}")
        check(
            "Resposta fora do contexto é exatamente a recusa padrão",
            resposta2.strip() == REFUSAL,
            f"obtido: {resposta2!r}",
        )

    section("4. Busca por similaridade (search.py) com k=10")
    resultados = search_similar_chunks("crédito e arrendamento mercantil", k=10)
    log(f"Quantidade de resultados retornados: {len(resultados)}")
    for i, (doc, score) in enumerate(resultados[:3], 1):
        log(f"  [{i}] score={score:.4f} trecho={doc.page_content[:80]!r}")
    check("search_similar_chunks respeita k<=10", len(resultados) <= 10)
    check("search_similar_chunks retorna pelo menos 1 resultado", len(resultados) >= 1)

    section("5. Anexando um segundo PDF (simula o comando 'anexar' do chat / upload da API)")
    os.makedirs(fixtures_dir, exist_ok=True)
    shutil.copyfile(pdf_path, segundo_pdf)
    log(f"Fixture de teste criada em '{segundo_pdf}' (cópia do document.pdf, só para validar o pipeline de anexação)")

    n2 = ingest_pdf(segundo_pdf)
    log(f">>> ingest_pdf('{segundo_pdf}') retornou: {n2} chunks")

    log("\n--- Log do container do banco (docker logs --tail 15) ---")
    log(docker_logs())

    log("\n--- Query de quantidade (total) ---")
    log(sql("SELECT count(*) FROM langchain_pg_embedding;"))

    log("\n--- Query de quantidade por arquivo de origem ---")
    log(sql("SELECT cmetadata->>'source' AS arquivo, count(*) FROM langchain_pg_embedding GROUP BY 1 ORDER BY 1;"))

    total_2 = int(sql_scalar("SELECT count(*) FROM langchain_pg_embedding;"))
    check(
        "Contagem total após anexar = ingestão inicial + novo PDF",
        total_2 == n1 + n2,
        f"esperado {n1 + n2}, obtido {total_2}",
    )

    section("6. Pergunta após anexar (base compartilhada deve continuar respondendo)")
    resposta3, erro3 = ask_seguro(pergunta1)
    log(f"PERGUNTA: {pergunta1}")
    if erro3:
        log(f"ERRO: {erro3}")
        results.append(("Ainda responde corretamente após anexar novo PDF", "ERROR", erro3))
    else:
        log(f"RESPOSTA: {resposta3}")
        check("Ainda responde corretamente após anexar novo PDF", resposta3.strip() != REFUSAL)


def cleanup():
    section("7. Limpeza (deixando o banco de volta só com document.pdf)")
    pdf_path = os.path.join(ROOT, "document.pdf")
    segundo_pdf = os.path.join(ROOT, "tests", "fixtures", "segundo_documento_teste.pdf")
    reset_db()
    n_final = ingest_pdf(pdf_path)
    log(f"Banco resetado e reingerido: {n_final} chunks (apenas document.pdf)")
    if os.path.exists(segundo_pdf):
        os.remove(segundo_pdf)
        log(f"Fixture de teste removida: {segundo_pdf}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        log()
        log(f"ERRO INESPERADO, interrompendo os testes: {exc}")
        results.append(("Execução completa sem erros inesperados", "FAIL", str(exc)))
    finally:
        try:
            cleanup()
        except Exception as exc:  # noqa: BLE001
            log(f"ERRO durante a limpeza: {exc}")

        section("Resumo")
        falhas = [r for r in results if r[1] in ("FAIL", "ERROR")]
        for nome, status, detalhe in results:
            log(f"[{status}] {nome}")
        log()
        if falhas:
            log(f"RESULTADO FINAL: {len(falhas)} item(ns) com problema (FAIL/ERROR).")
        else:
            log("RESULTADO FINAL: todos os testes passaram.")

        with open(EVIDENCE_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")

        log(f"\nEvidências salvas em: {EVIDENCE_PATH}")

        sys.exit(1 if falhas else 0)
