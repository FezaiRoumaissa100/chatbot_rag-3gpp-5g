import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.generation.prompt import REFUSAL_MESSAGE, SYSTEM_PROMPT, format_context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class GeminiGenerator:
    """Generates grounded, cited answers from 3GPP chunks using Gemini Flash."""

    def __init__(
        self,
        model_name: str = "gemini-3.5-flash",
        temperature: float = 0.0,
        min_rerank_score: float = -4.0,
    ):
        api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing API key: please set LLM_API_KEY in your .env file."
            )

        self.model_name = model_name
        self.temperature = temperature
        self.min_rerank_score = min_rerank_score
        self.client = genai.Client(api_key=api_key)

    def generate(self, query: str, chunks: list[dict]) -> str:
        if not chunks:
            return REFUSAL_MESSAGE

        context_text = format_context(chunks)
        user_prompt = (
            f"3GPP NORMATIVE CONTEXT:\n"
            f"{context_text}\n\n"
            f"USER QUESTION:\n"
            f"{query}\n\n"
            f"ANSWER (in English, strictly grounded with [Spec, Section] citations):"
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=self.temperature,
            ),
        )

        answer = (response.text or "").strip()
        return answer if answer else REFUSAL_MESSAGE