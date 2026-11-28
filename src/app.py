"""FastAPI backend: /chat (JSON), /chat/stream (SSE), /models, /corpus, /health."""
import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.generation.llm import LLMError, list_available_llms

pipeline = None
_lock = threading.Lock()


def get_pipeline():
    global pipeline
    with _lock:
        if pipeline is None:
            from src.pipeline import RAGPipeline
            pipeline = RAGPipeline()
    return pipeline


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=get_pipeline, daemon=True).start()   # warm models in the background
    yield


app = FastAPI(title="RAG 3GPP 5G Chatbot", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Turn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = None
    history: list[Turn] = []
    llm: str | None = None
    release: str = "auto"          # auto | 18 | 17 | compare


def _err(e: Exception) -> tuple[int, str, str]:
    if isinstance(e, LLMError):
        return e.status, e.code, str(e)
    if isinstance(e, RuntimeError):
        return 503, "INDEX_MISSING", str(e)
    return 500, "ERROR", "Something went wrong. Please try again."


@app.get("/health")
def health():
    return {"status": "ok", "ready": pipeline is not None}


@app.get("/models")
def models():
    return list_available_llms()


@app.get("/corpus")
def corpus():
    if pipeline is None:
        raise HTTPException(503, "WARMING_UP: models are still loading")
    return {"documents": pipeline.retriever.corpus_info(), "default_release": pipeline.retriever.default_release}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        return get_pipeline().run(req.query, req.top_k, [t.model_dump() for t in req.history], req.llm, req.release)
    except Exception as e:
        status, code, msg = _err(e)
        raise HTTPException(status, f"{code}: {msg}")


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    history = [t.model_dump() for t in req.history]

    def events():
        try:
            for ev in get_pipeline().stream(req.query, req.top_k, history, req.llm, req.release):
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
        except Exception as e:
            status, code, msg = _err(e)
            yield f"event: error\ndata: {json.dumps({'status': status, 'code': code, 'detail': msg})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
