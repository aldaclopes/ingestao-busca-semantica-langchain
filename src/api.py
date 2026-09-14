import os
import shutil
import sys
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
from chat import answer_question, friendly_error_message
from ingest import ingest_pdf

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = FastAPI(title="Ingestão e Busca Semântica - API")


class Pergunta(BaseModel):
    pergunta: str


@app.post("/api/ask")
def ask(payload: Pergunta):
    try:
        resposta = answer_question(payload.pergunta)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=friendly_error_message(exc)) from exc
    return {"resposta": resposta}


@app.post("/api/ingest")
def ingest(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .pdf")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        n_chunks = ingest_pdf(tmp_path)
    finally:
        os.remove(tmp_path)

    return {"arquivo": file.filename, "chunks": n_chunks}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
