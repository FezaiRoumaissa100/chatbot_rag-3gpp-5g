from typing import Iterator

from src.generation.llm import BaseLLM, get_llm
from src.generation.prompt import REFUSAL_MESSAGE, build_system_prompt, format_context


class RAGGenerator:
    """Builds the grounded prompt and calls any LLM provider (Gemini API or local Ollama)."""

    def __init__(self, llm: BaseLLM | str | None = None, temperature: float = 0.0):
        self.llm = llm if isinstance(llm, BaseLLM) else get_llm(llm)
        self.temperature = temperature

    def build(self, query: str, chunks: list[dict], compare: bool = False) -> tuple[str, str]:
        releases = {str(c["metadata"].get("release", "")) for c in chunks}
        system = build_system_prompt(multi_release=len(releases) > 1, compare=compare)
        user = (f"3GPP NORMATIVE CONTEXT:\n{format_context(chunks)}\n\n"
                f"USER QUESTION:\n{query}\n\n"
                f"ANSWER (English, strictly grounded, with [Spec, Section] citations):")
        return system, user

    def generate(self, query: str, chunks: list[dict], compare: bool = False) -> str:
        if not chunks:
            return REFUSAL_MESSAGE
        system, user = self.build(query, chunks, compare)
        return self.llm.generate(system, user, self.temperature) or REFUSAL_MESSAGE

    def stream(self, query: str, chunks: list[dict], compare: bool = False) -> Iterator[str]:
        if not chunks:
            yield REFUSAL_MESSAGE
            return
        system, user = self.build(query, chunks, compare)
        yield from self.llm.stream(system, user, self.temperature)


class GeminiGenerator(RAGGenerator):
    """Backward-compatible alias used by older scripts/tests."""

    def __init__(self, model_name: str = "gemini-3.5-flash-lite", temperature: float = 0.0, **_):
        super().__init__(f"gemini:{model_name}", temperature)
