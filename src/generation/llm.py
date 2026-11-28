"""LLM providers behind one interface: Gemini (API) and Ollama (local).

Spec strings:  "gemini:gemini-3.5-flash-lite"   "ollama:qwen2.5:7b-instruct"
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Iterator

import httpx
from dotenv import load_dotenv

from src.config import PROJECT_ROOT, cfg

load_dotenv(PROJECT_ROOT / ".env")


class LLMError(Exception):
    def __init__(self, message: str, status: int = 502, code: str = "UPSTREAM_ERROR"):
        super().__init__(message)
        self.status, self.code = status, code


def load_gemini_keys() -> list[str]:
    multi = os.getenv("LLM_API_KEYS", "")
    if multi.strip():
        return [k.strip() for k in multi.split(",") if k.strip()]
    single = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return [single] if single else []


class BaseLLM:
    provider, model = "base", ""

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    def generate(self, system: str, user: str, temperature: float = 0.0) -> str:
        raise NotImplementedError

    def stream(self, system: str, user: str, temperature: float = 0.0) -> Iterator[str]:
        yield self.generate(system, user, temperature)


class GeminiLLM(BaseLLM):
    provider = "gemini"

    def __init__(self, model: str, keys: list[str] | None = None):
        from google import genai
        from google.genai import types
        self._genai, self._types = genai, types
        self.model = model
        self.keys = keys or load_gemini_keys()
        if not self.keys:
            raise LLMError("No Gemini API key. Set LLM_API_KEYS or LLM_API_KEY in .env.", 503, "NO_API_KEY")
        self.idx = 0
        self._build()

    def _build(self):
        self.client = self._genai.Client(api_key=self.keys[self.idx])

    def _rotate(self) -> bool:
        if self.idx + 1 < len(self.keys):
            self.idx += 1
            self._build()
            return True
        return False

    def _cfg(self, system, temperature):
        return self._types.GenerateContentConfig(system_instruction=system, temperature=temperature)

    def _guard(self, fn):
        from google.genai import errors
        for attempt in range(4):
            try:
                return fn()
            except errors.ClientError as e:
                if e.code == 429:
                    if self._rotate():
                        continue
                    raise LLMError("Model usage limit reached. Try again later or switch model.", 429, "QUOTA_EXCEEDED") from e
                raise LLMError("The AI service rejected the request.", 502, "UPSTREAM_ERROR") from e
            except errors.ServerError as e:
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise LLMError("The AI service is overloaded. Try again in a moment.", 503, "OVERLOADED") from e

    def generate(self, system, user, temperature=0.0):
        r = self._guard(lambda: self.client.models.generate_content(
            model=self.model, contents=user, config=self._cfg(system, temperature)))
        return (r.text or "").strip()

    def stream(self, system, user, temperature=0.0):
        def open_stream():
            return self.client.models.generate_content_stream(
                model=self.model, contents=user, config=self._cfg(system, temperature))
        for chunk in self._guard(open_stream):
            if chunk.text:
                yield chunk.text


class ThinkStripper:
    """Removes <think>...</think> blocks (reasoning models) from a token stream."""
    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.buf, self.inside = "", False

    def feed(self, piece: str) -> str:
        self.buf += piece
        out, keep = "", len(self.OPEN) - 1
        while True:
            if self.inside:
                j = self.buf.find(self.CLOSE)
                if j == -1:
                    self.buf = self.buf[-len(self.CLOSE):]
                    return out
                self.buf, self.inside = self.buf[j + len(self.CLOSE):], False
            else:
                i = self.buf.find(self.OPEN)
                if i == -1:
                    if len(self.buf) > keep:
                        out, self.buf = out + self.buf[:-keep], self.buf[-keep:]
                    return out
                out, self.buf, self.inside = out + self.buf[:i], self.buf[i + len(self.OPEN):], True

    def flush(self) -> str:
        out = "" if self.inside else self.buf
        self.buf = ""
        return out


def _norm_host(host: str) -> str:
    host = host.strip().rstrip("/")
    return host if host.startswith("http") else f"http://{host}"


def ollama_host() -> str:
    return _norm_host(os.getenv("OLLAMA_HOST") or cfg("generation")["ollama_host"])


def list_ollama_models(host: str | None = None) -> tuple[bool, list[str]]:
    try:
        r = httpx.get(f"{host or ollama_host()}/api/tags", timeout=1.5)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        skip = ("embed", "bge", "nomic", "minilm", "e5")
        return True, [n for n in names if not any(s in n.lower() for s in skip)]
    except Exception:
        return False, []


class OllamaLLM(BaseLLM):
    provider = "ollama"

    def __init__(self, model: str, host: str | None = None, num_ctx: int | None = None):
        self.model = model
        self.host = _norm_host(host) if host else ollama_host()
        self.num_ctx = num_ctx or cfg("generation")["ollama_num_ctx"]

    def _payload(self, system, user, temperature, stream):
        return {"model": self.model, "stream": stream, "keep_alive": "30m",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                # Ollama's default context (2k-4k) silently truncates 15 chunks: always set num_ctx.
                "options": {"temperature": temperature, "num_ctx": self.num_ctx}}

    def _fail(self, e: Exception):
        if isinstance(e, httpx.ConnectError):
            raise LLMError(f"Ollama is not reachable at {self.host}. Start it with `ollama serve`.", 503, "OLLAMA_DOWN") from e
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            raise LLMError(f"Model '{self.model}' is not installed. Run `ollama pull {self.model}`.", 404, "MODEL_MISSING") from e
        raise LLMError(f"Ollama error: {e}", 502, "UPSTREAM_ERROR") from e

    def generate(self, system, user, temperature=0.0):
        try:
            r = httpx.post(f"{self.host}/api/chat", json=self._payload(system, user, temperature, False),
                           timeout=httpx.Timeout(900, connect=5))
            r.raise_for_status()
            text = r.json()["message"]["content"]
        except Exception as e:
            self._fail(e)
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    def stream(self, system, user, temperature=0.0):
        strip = ThinkStripper()
        try:
            with httpx.stream("POST", f"{self.host}/api/chat", json=self._payload(system, user, temperature, True),
                              timeout=httpx.Timeout(900, connect=5)) as r:
                if r.status_code >= 400:
                    r.read()
                    r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    piece = strip.feed(data.get("message", {}).get("content", ""))
                    if piece:
                        yield piece
                    if data.get("done"):
                        break
        except LLMError:
            raise
        except Exception as e:
            self._fail(e)
        tail = strip.flush()
        if tail:
            yield tail


_CACHE: dict[str, BaseLLM] = {}


def get_llm(spec: str | None = None) -> BaseLLM:
    spec = spec or cfg("generation")["default_llm"]
    provider, _, model = spec.partition(":")
    if provider not in ("gemini", "ollama"):
        provider, model = "gemini", spec
    key = f"{provider}:{model}"
    if key not in _CACHE:
        _CACHE[key] = GeminiLLM(model) if provider == "gemini" else OllamaLLM(model)
    return _CACHE[key]


def list_available_llms() -> dict:
    g = cfg("generation")
    has_key = bool(load_gemini_keys())
    items = [{"id": f"gemini:{m}", "provider": "gemini", "label": m, "available": has_key}
             for m in g["gemini_models"]]
    reachable, names = list_ollama_models()
    items += [{"id": f"ollama:{n}", "provider": "ollama", "label": n, "available": True} for n in names]
    return {"default": g["default_llm"], "models": items,
            "ollama": {"host": ollama_host(), "reachable": reachable}}
