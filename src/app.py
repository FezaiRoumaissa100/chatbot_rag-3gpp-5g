"""FastAPI backend exposing the 3GPP RAG chatbot."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# Accept LLM_API_KEYS (plural) as a fallback for LLM_API_KEY
if not os.getenv("LLM_API_KEY") and not os.getenv("GEMINI_API_KEY"):
    keys = os.getenv("LLM_API_KEYS", "").split(",")
    if keys and keys[0].strip():
        os.environ["LLM_API_KEY"] = keys[0].strip()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.genai import errors as genai_errors
from pydantic import BaseModel

app = FastAPI(title="RAG 3GPP 5G Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = None


def get_pipeline():
    global pipeline
    if pipeline is None:
        from src.pipeline import RAGPipeline

        pipeline = RAGPipeline()
    return pipeline


class ChatRequest(BaseModel):
    query: str
    top_k: int | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        return get_pipeline().run(req.query, top_k=req.top_k)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except genai_errors.ClientError as e:
        if e.code == 429:
            raise HTTPException(
                status_code=429,
                detail="QUOTA_EXCEEDED: You've reached the model's usage limit. Please try again later.",
            )
        raise HTTPException(status_code=502, detail="UPSTREAM_ERROR: The AI service returned an error. Please try again.")
    except genai_errors.ServerError as e:
        raise HTTPException(
            status_code=503,
            detail="OVERLOADED: The AI service is currently overloaded. Please try again in a moment.",
        )
    except Exception:
        raise HTTPException(status_code=500, detail="ERROR: Something went wrong. Please try again.")
