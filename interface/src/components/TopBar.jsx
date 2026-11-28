import { useEffect, useRef, useState } from 'react'
import Icon from './icons.jsx'

const RELEASES = [
  ['auto', 'Auto'],
  ['18', 'Rel-18'],
  ['17', 'Rel-17'],
  ['compare', 'Compare'],
]

const STATUS = {
  connecting: 'Connecting',
  warming: 'Loading models',
  ready: 'Ready',
  offline: 'Backend offline',
}

export default function TopBar({ settings, update, models, corpus, health, canReset, onReset }) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    const close = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  const have17 = !corpus || corpus.documents.some((d) => d.release === '17')
  const idx = Math.max(0, RELEASES.findIndex(([v]) => v === settings.release))
  const current = models?.models.find((m) => m.id === settings.llm)
  const label = current?.label || settings.llm.split(':').slice(1).join(':')

  return (
    <header className="nav glass">
      <div className="brand">
        <span className={`dot ${health}`} title={STATUS[health]} />
        <span className="brand-name">ChatGPP</span>
      </div>

      <div className="seg" style={{ '--i': idx }} role="radiogroup" aria-label="Specification release">
        <span className="thumb" />
        {RELEASES.map(([v, text]) => {
          const disabled = (v === '17' || v === 'compare') && !have17
          return (
            <button key={v} role="radio" aria-checked={settings.release === v} disabled={disabled}
              title={disabled ? 'Release 17 is not indexed yet' : undefined}
              className={settings.release === v ? 'on' : ''} onClick={() => update({ release: v })}>
              {text}
            </button>
          )
        })}
      </div>

      <div className="menu-wrap" ref={menuRef}>
        <button className="pill" onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open}>
          <Icon name={settings.llm.startsWith('ollama') ? 'chip' : 'cloud'} size={15} />
          <span className="pill-label">{label}</span>
          <Icon name="chevron" size={14} />
        </button>
        {open && (
          <div className="menu glass" role="listbox">
            {['gemini', 'ollama'].map((prov) => {
              const items = models?.models.filter((m) => m.provider === prov) || []
              return (
                <div key={prov} className="menu-group">
                  <div className="menu-title">{prov === 'gemini' ? 'Cloud · Gemini API' : 'On this computer · Ollama'}</div>
                  {items.length === 0 && (
                    <div className="menu-empty">
                      {prov === 'ollama'
                        ? models?.ollama.reachable ? 'No model installed. Run ollama pull qwen2.5:7b-instruct' : 'Ollama isn’t running'
                        : 'No models listed'}
                    </div>
                  )}
                  {items.map((m) => (
                    <button key={m.id} role="option" aria-selected={m.id === settings.llm} disabled={!m.available}
                      className={`menu-item ${m.id === settings.llm ? 'on' : ''}`}
                      onClick={() => { update({ llm: m.id }); setOpen(false) }}>
                      <span>{m.label}</span>
                      {m.id === settings.llm && <Icon name="check" size={15} />}
                      {!m.available && <small>no API key</small>}
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <button className="icon-btn" onClick={() => update({ theme: settings.theme === 'dark' ? 'light' : 'dark' })}
        aria-label="Toggle light or dark theme">
        <Icon name={settings.theme === 'dark' ? 'sun' : 'moon'} size={17} />
      </button>
      {canReset && (
        <button className="icon-btn" onClick={onReset} aria-label="New chat" title="New chat">
          <Icon name="plus" size={18} />
        </button>
      )}
    </header>
  )
}
