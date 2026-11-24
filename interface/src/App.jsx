import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function RobotIcon({ size = 28 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <path d="M12 8V4" />
      <circle cx="12" cy="3" r="1" />
      <circle cx="9" cy="13" r="0.5" fill="currentColor" />
      <circle cx="15" cy="13" r="0.5" fill="currentColor" />
      <path d="M9 17h6" />
      <path d="M2 13v3" />
      <path d="M22 13v3" />
    </svg>
  )
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  const hasMessages = messages.length > 0 || loading

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage(e) {
    e?.preventDefault()
    const query = input.trim()
    if (!query || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: query }])
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.answer,
          sources: data.sources,
          routing: data.routing,
          latency_ms: data.latency_ms,
        },
      ])
    } catch (err) {
      const raw = err.message || ''
      const msg = raw.includes('fetch')
        ? 'Unable to reach the server. Please check that the backend is running and try again.'
        : raw.replace(/^[A-Z_]+:\s*/, '') || 'Something went wrong. Please try again.'
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: msg, error: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-icon">
          <RobotIcon size={26} />
        </div>
        <div>
          <div className="header-title">ChatGPP</div>
          <div className="header-subtitle">
            TS 23.501 · TS 24.501 — Release 18
          </div>
        </div>
      </header>

      <main className={`chat-area ${hasMessages ? '' : 'centered'}`}>

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.role === 'assistant' && (
              <div className="avatar assistant">
                <RobotIcon size={18} />
              </div>
            )}
            <div className="message-content">
              {msg.role === 'user' ? (
                <div>{msg.text}</div>
              ) : (
                <div className="answer-text">
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message assistant">
            <div className="avatar assistant">
              <RobotIcon size={18} />
            </div>
            <div className="message-content">
              <div className="typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      <footer className={`input-area ${hasMessages ? '' : 'centered'}`}>
        <form className="input-wrapper" onSubmit={sendMessage}>
          <textarea
            className="chat-input"
            placeholder="Ask a question about 5G (e.g. What is the role of the AMF?)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={loading}
          />
          <button
            className="send-button"
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send"
          >
            ↑
          </button>
        </form>
      </footer>
    </div>
  )
}
