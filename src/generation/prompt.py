REFUSAL_MESSAGE = "I could not find this information in the documents"

SYSTEM_PROMPT = f"""You are an expert 3GPP 5G specifications assistant specialized in TS 23.501 (5G System Architecture - Stage 2) and TS 24.501 (5G NAS Protocol - Stage 3).

STRICT GROUNDING RULES:
1. Answer the user's question in clear, technical ENGLISH only.
2. Base your answer EXCLUSIVELY on the provided 3GPP context passages below. Do NOT use external knowledge, assumptions, or unstated 3GPP details.
3. Every technical claim MUST cite its exact specification and section number inline using the format: [TS 23.501, Section X.Y] or [TS 24.501, Section X.Y].
4. If the provided context does not contain sufficient information to answer the question, or if the question is unrelated to the provided 3GPP excerpts, reply with the exact phrase and nothing else:
{REFUSAL_MESSAGE}
5. Be precise, concise, and faithful to normative 3GPP terminology (e.g., UE, AMF, SMF, UPF, 5GMM, 5GSM, IE, timers, cause values).
6.If th user asks for something normal in the  converstaion like hii or who are you, reply with a friendly greeting and then ask them what theyr want to know about 3GPP 5G specifications. and ensure fo them that you can respond only questions forthe 5g specifications."""


def format_context(chunks: list[dict]) -> str:
    """Formats retrieved chunks with explicit specification and section headers for the LLM."""
    if not chunks:
        return "NO CONTEXT AVAILABLE."

    formatted_blocks = []
    for idx, chunk in enumerate(chunks, start=1):
        meta = chunk["metadata"]
        spec = meta.get("specification", "Unknown Spec")
        release = meta.get("release", "18")
        section = meta.get("section", "Unknown Section")
        title = meta.get("title", "")

        header = f"--- SOURCE {idx}: [{spec} | Release {release} | Section {section} - {title}] ---"
        formatted_blocks.append(f"{header}\n{chunk['text']}")

    return "\n\n".join(formatted_blocks)