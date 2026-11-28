## Ollama (local LLM)
Start Ollama, pull a model, then pick it in the top bar of the UI (or `--llms ollama:<model>` in eval_04).
Context window is set to 16k (`generation.ollama_num_ctx`) because Ollama's default silently truncates 15 chunks.
For small models use fewer chunks: `python evaluation/eval_04_llm_comparison.py --k 8 ...`.

## Releases
`Auto` (default Rel-18, detects "Rel-17" in the question), `Rel-18`, `Rel-17`, `Compare` (retrieves both releases and asks the LLM for Unchanged / Changed / Only-in structure).

## API
`POST /chat/stream` (SSE: meta, sources, token, done, error), `POST /chat`, `GET /models`, `GET /corpus`, `GET /health`.
