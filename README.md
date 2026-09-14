# Atividade acadêmica
Curso: MBA em Engenharia de Software com IA
Turma: 6
Aluna: Alda Monte

# Ingestão e Busca Semântica com LangChain e Postgres

Ingestão de um PDF em um banco PostgreSQL com pgVector e busca semântica via CLI, usando LangChain e Google Gemini.

## Tecnologias

- Python
- LangChain (`langchain`, `langchain-community`, `langchain-postgres`, `langchain-google-genai`, `langchain-text-splitters`)
- PostgreSQL + pgVector (via Docker)
- Google Gemini (embeddings e LLM)

## Pré-requisitos

- Python 3.10+ (funciona em 3.9, mas com avisos de fim de suporte das libs do Google)
- Docker e Docker Compose
- Uma API Key do Google AI Studio: https://aistudio.google.com/apikey

## Configuração

1. Crie e ative um ambiente virtual:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Copie o arquivo de variáveis de ambiente e preencha sua API Key:

   ```bash
   cp .env.example .env
   ```

   Edite o `.env` e preencha `GOOGLE_API_KEY`.

   > **Atenção:** os nomes dos modelos do Gemini mudam com frequência. Antes de rodar, confirme quais modelos sua chave suporta:
   >
   > ```bash
   > curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY"
   > ```
   >
   > Ajuste `GOOGLE_EMBEDDING_MODEL` (precisa suportar `embedContent`) e `GOOGLE_LLM_MODEL` (precisa suportar `generateContent`) no `.env` conforme o resultado.

4. Coloque o PDF que deseja consultar na raiz do projeto com o nome `document.pdf` (ou ajuste `PDF_PATH` no `.env`).

## Execução

1. Suba o banco de dados:

   ```bash
   docker compose up -d
   ```

2. Rode a ingestão do PDF (só precisa rodar uma vez por PDF/modelo de embeddings):

   ```bash
   python src/ingest.py
   ```

3. Rode o chat:

   ```bash
   python src/chat.py
   ```

   Exemplo de uso:

   ```
   PERGUNTA: Qual o assunto tratado neste documento?
   RESPOSTA: ...

   PERGUNTA: Qual a capital da França?
   RESPOSTA: Não tenho informações necessárias para responder sua pergunta.
   ```

   Digite `sair` para encerrar.

### Anexando novos PDFs durante o chat

Dentro do chat, é possível ingerir um novo PDF sem sair do programa:

```
PERGUNTA: anexar /caminho/para/outro-arquivo.pdf
Lendo e indexando '/caminho/para/outro-arquivo.pdf'...
Ingestão concluída: 4 chunks de '/caminho/para/outro-arquivo.pdf' salvos no banco.
Pronto: 4 chunks adicionados ao banco. Já pode perguntar sobre ele.
```

O PDF anexado passa pelo mesmo pipeline do `ingest.py` (split em chunks de 1000/150 + embeddings) e é gravado na **mesma base** já usada pelo `document.pdf` original — ou seja, fica disponível permanentemente, mesmo em execuções futuras do chat, e as perguntas passam a poder ser respondidas com base em qualquer um dos PDFs já ingeridos.

## Interface web (opcional)

Além do CLI (obrigatório pelo desafio), o projeto tem uma interface de chat simples no navegador, para facilitar testes manuais. Ela roda inteiramente local, junto com o restante do projeto.

Com o banco já rodando (`docker compose up -d`) e as dependências instaladas, suba a API:

```bash
python src/api.py
```

Abra **http://localhost:8000** no navegador. A página permite:
- Digitar perguntas e ver a resposta, como no CLI.
- Clicar no clipe (📎) para anexar um novo PDF, que é ingerido no mesmo banco (mesma lógica do comando `anexar` do CLI) e passa a poder ser consultado.

Arquitetura: `frontend/index.html` é uma página estática (HTML/CSS/JS puro, sem build) que fala com o backend só por HTTP (`fetch`), nos endpoints:
- `POST /api/ask` — `{"pergunta": "..."}` → `{"resposta": "..."}`
- `POST /api/ingest` — upload multipart do PDF → `{"arquivo": ..., "chunks": ...}`

O backend (`src/api.py`, feito com FastAPI) não duplica lógica: só expõe `answer_question()` (de `chat.py`) e `ingest_pdf()` (de `ingest.py`) como rotas HTTP.

## Testes automatizados

```bash
python tests/run_tests.py
```

O script roda o fluxo completo de ponta a ponta (reset do banco → ingestão → pergunta dentro do contexto → pergunta fora do contexto → busca → anexar um segundo PDF → nova pergunta → limpeza), com verificações automáticas (PASS/FAIL) em cada etapa. A cada ingestão, ele registra no log o output do `docker logs` do container e a query de contagem de chunks no banco.

> Atenção: o script reseta o banco (`docker compose down -v`) para garantir um resultado determinístico, e o deixa de volta só com `document.pdf` ao final — mesmo se algum teste falhar no meio do caminho.

Cada execução salva um relatório completo (evidência) em `tests/evidencias/evidencia_<timestamp>.txt`. Se algum teste que depende do LLM falhar com erro de cota (`ResourceExhausted` / `429`), é um limite gratuito diário do modelo escolhido, não um bug — espere o reset da cota ou troque `GOOGLE_LLM_MODEL` no `.env` por um modelo com cota disponível.

## Trocando de modelo de embeddings

Modelos de embedding diferentes geram vetores com dimensões diferentes. A tabela de vetores é criada na primeira ingestão já com a dimensão do modelo usado naquele momento. Se você trocar `GOOGLE_EMBEDDING_MODEL` depois de já ter ingerido dados, a ingestão passa a falhar por incompatibilidade de dimensão. Para recomeçar do zero:

```bash
docker compose down -v
docker compose up -d
python src/ingest.py
```

## Estrutura do projeto

```
├── docker-compose.yml   # Sobe o Postgres com pgVector
├── requirements.txt     # Dependências Python
├── .env.example         # Template das variáveis de ambiente
├── src/
│   ├── ingest.py         # Lê o PDF, divide em chunks e salva os embeddings no banco
│   ├── search.py         # Busca por similaridade no banco vetorial
│   ├── chat.py           # CLI de perguntas e respostas
│   ├── api.py            # (opcional) API HTTP para a interface web
├── frontend/
│   └── index.html         # (opcional) interface de chat no navegador
├── tests/
│   ├── run_tests.py       # Teste automatizado de ponta a ponta
│   └── evidencias/         # Relatórios gerados a cada execução dos testes
├── document.pdf          # PDF ingerido
└── README.md
```
