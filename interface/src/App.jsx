import { useCallback, useEffect, useRef, useState } from 'react'
import Hero from './components/Hero.jsx'
import Message from './components/Message.jsx'
import Composer from './components/Composer.jsx'
import TopBar from './components/TopBar.jsx'
import { Inspector } from './components/Sources.jsx'
import { cleanError, fetchCorpus, fetchHealth, fetchModels, streamChat } from './lib/api.js'

const uid = () => Math.random().toString(36).slice(2, 10)
const STORE = 'chatgpp.settings.v2'

function useSettings() {
  const [s, setS] = useState(() => {
    try { return { llm: 'gemini:gemini-3.5-flash-lite', release: 'auto', theme: 'dark', ...JSON.parse(localStorage.getItem(STORE) || '{}') } }
    catch { return { llm: 'gemini:gemini-3.5-flash-lite', release: 'auto', theme: 'dark' } }
  })
  useEffect(() => {
    document.documentElement.dataset.theme = s.theme
    try { localStorage.setItem(STORE, JSON.stringify(s)) } catch { /* private mode */ }
  }, [s])
  return [s, (patch) => setS((p) => ({ ...p, ...patch }))]
}

export default function App() {
  const [settings, update] = useSettings()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState('connecting')
  const [models, setModels] = useState(null)
  const [corpus, setCorpus] = useState(null)
  const [inspect, setInspect] = useState(null) // { msgId, index }

  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const stick = useRef(true)

  // ---- backend status -------------------------------------------------
  useEffect(() => {
    let alive = true
    let timer
    const tick = async () => {
      try {
        const h = await fetchHealth()
        if (!alive) return
        if (h.ready) {
          setHealth('ready')
          fetchModels().then((m) => alive && setModels(m)).catch(() => {})
          fetchCorpus().then((c) => alive && setCorpus(c)).catch(() => {})
          return
        }
        setHealth('warming')
      } catch { if (alive) setHealth('offline') }
      timer = setTimeout(tick, 2500)
    }
    tick()
    return () => { alive = false; clearTimeout(timer) }
  }, [])

  // pointer-following highlight on glass surfaces
  useEffect(() => {
    const move = (e) => {
      const el = e.target.closest?.('.glow')
      if (!el) return
      const r = el.getBoundingClientRect()
      el.style.setProperty('--mx', `${e.clientX - r.left}px`)
      el.style.setProperty('--my', `${e.clientY - r.top}px`)
    }
    document.addEventListener('pointermove', move, { passive: true })
    return () => document.removeEventListener('pointermove', move)
  }, [])

  // keep the view pinned to the bottom while streaming, unless the reader scrolled up
  useEffect(() => {
    const el = scrollRef.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [messages])

  const onScroll = () => {
    const el = scrollRef.current
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140
  }

  const patch = useCallback((id, fn) => {
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...fn(m) } : m)))
  }, [])

  const send = useCallback(async (text) => {
    const query = (text ?? input).trim()
    if (!query || busy) return
    setInput('')
    setBusy(true)
    stick.current = true

    const history = messages
      .filter((m) => m.text && m.status !== 'error')
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.text.slice(0, 1200) }))
    const aid = uid()
    setMessages((ms) => [
      ...ms,
      { id: uid(), role: 'user', text: query },
      { id: aid, role: 'assistant', text: '', status: 'streaming', stage: 'analyzing', sources: [], meta: null, done: null },
    ])

    // tokens arrive faster than React should render: flush ~25 times a second
    let buffer = ''
    let timer = null
    const flush = () => {
      timer = null
      if (!buffer) return
      const chunk = buffer
      buffer = ''
      patch(aid, (m) => ({ text: m.text + chunk, stage: 'writing' }))
    }

    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamChat({
        query, history, llm: settings.llm, release: settings.release, signal: controller.signal,
        onEvent: (ev, data) => {
          if (ev === 'meta') patch(aid, () => ({ meta: data }))
          else if (ev === 'sources') patch(aid, () => ({ sources: data, stage: 'reading' }))
          else if (ev === 'token') { buffer += data; if (!timer) timer = setTimeout(flush, 40) }
          else if (ev === 'done') { clearTimeout(timer); flush(); patch(aid, () => ({ done: data, status: 'done', stage: 'done' })) }
          else if (ev === 'error') { clearTimeout(timer); flush(); patch(aid, () => ({ status: 'error', error: cleanError(`${data.code}: ${data.detail}`) })) }
        },
      })
    } catch (e) {
      clearTimeout(timer)
      flush()
      if (e.name === 'AbortError') patch(aid, () => ({ status: 'stopped' }))
      else patch(aid, () => ({ status: 'error', error: e.message }))
    } finally {
      patch(aid, (m) => (m.status === 'streaming' ? { status: 'done' } : {}))
      abortRef.current = null
      setBusy(false)
    }
  }, [input, busy, messages, settings.llm, settings.release, patch])

  const stop = () => abortRef.current?.abort()
  const reset = () => { abortRef.current?.abort(); setMessages([]); setInspect(null) }

  const openSource = useCallback((msgId, index) => setInspect({ msgId, index }), [])
  const inspectMsg = inspect && messages.find((m) => m.id === inspect.msgId)
  const sources = inspectMsg?.sources || []
  const step = (d) => setInspect((cur) => cur && { ...cur, index: (cur.index + d + sources.length) % sources.length })

  const empty = messages.length === 0

  return (
    <div className="app">
      <div className="aurora" aria-hidden="true"><i className="a1" /><i className="a2" /><i className="a3" /><i className="grid" /></div>

      <TopBar settings={settings} update={update} models={models} corpus={corpus} health={health}
        canReset={!empty} onReset={reset} />

      <main className="scroller" ref={scrollRef} onScroll={onScroll}>
        {empty ? (
          <Hero corpus={corpus} onPick={(q) => send(q)} />
        ) : (
          <div className="thread">
            {messages.map((m) => (
              <Message key={m.id} msg={m} onOpenSource={openSource}
                activeSource={inspect?.msgId === m.id ? inspect.index : null} />
            ))}
          </div>
        )}
      </main>

      <Composer value={input} onChange={setInput} onSend={() => send()} onStop={stop} busy={busy}
        disabled={health === 'offline'} />

      <Inspector sources={sources} index={inspectMsg ? inspect.index : null}
        onClose={() => setInspect(null)} onStep={step} />
    </div>
  )
}
