export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function getJSON(path) {
  const res = await fetch(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const fetchHealth = () => getJSON('/health')
export const fetchModels = () => getJSON('/models')
export const fetchCorpus = () => getJSON('/corpus')

function cleanError(raw) {
  return (raw || '').replace(/^[A-Z_]+:\s*/, '') || 'Something went wrong. Please try again.'
}

/** POST /chat/stream and dispatch Server-Sent Events: meta, sources, token, done, error. */
export async function streamChat({ query, history, llm, release, signal, onEvent }) {
  let res
  try {
    res = await fetch(`${API_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, history, llm, release }),
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error('Can’t reach the server. Check that the backend is running on ' + API_URL + '.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(cleanError(body.detail))
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (data) onEvent(event, JSON.parse(data))
    }
  }
}

export { cleanError }
