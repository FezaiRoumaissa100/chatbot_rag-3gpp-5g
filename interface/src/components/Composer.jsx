import { useEffect, useRef } from 'react'
import Icon from './icons.jsx'

export default function Composer({ value, onChange, onSend, onStop, busy, disabled }) {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [value])

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      if (!busy) onSend()
    }
  }

  return (
    <div className="dock">
      <form className="composer glass" onSubmit={(e) => { e.preventDefault(); busy ? onStop() : onSend() }}>
        <textarea ref={ref} rows={1} value={value} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown}
          placeholder="Ask about the 5G specifications, in English or French" aria-label="Your question" autoFocus />
        <button type="submit" className={`send ${busy ? 'stop' : ''}`} disabled={!busy && (disabled || !value.trim())}
          aria-label={busy ? 'Stop generating' : 'Send'}>
          <Icon name={busy ? 'stop' : 'arrow'} size={busy ? 18 : 19} stroke={2.2} />
        </button>
      </form>
      <p className="fineprint">Answers are generated from the specifications. Check the cited section for anything critical.</p>
    </div>
  )
}
