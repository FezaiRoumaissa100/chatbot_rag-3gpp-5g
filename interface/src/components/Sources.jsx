import { useEffect } from 'react'
import Icon from './icons.jsx'
import { SPEC_COLOR } from '../lib/cite.js'

export function SourceStrip({ sources, cited, active, onOpen }) {
  const scores = sources.map((s) => s.rerank_score).filter((v) => v != null)
  const lo = Math.min(...scores), hi = Math.max(...scores)
  const norm = (v) => (v == null || hi === lo ? 0.6 : 0.15 + 0.85 * ((v - lo) / (hi - lo)))
  const order = sources.map((_, i) => i).sort((a, b) => (cited.has(b) ? 1 : 0) - (cited.has(a) ? 1 : 0) || a - b)

  return (
    <div className="sources">
      <div className="sources-head">
        <span>Sources</span>
        <small>{cited.size ? `${cited.size} cited, ${sources.length - cited.size} also read` : `${sources.length} passages read`}</small>
      </div>
      <div className="strip">
        {order.map((i) => {
          const s = sources[i], m = s.metadata
          return (
            <button key={s.chunk_id} id={`src-${i}`} className={`src glass glow ${active === i ? 'active' : ''} ${cited.has(i) ? 'cited' : ''}`}
              style={{ '--c': SPEC_COLOR[m.specification] || 'var(--blue)' }} onClick={() => onOpen(i)}>
              <span className="src-top">
                <i className="src-dot" />
                <b>{m.specification.replace('TS ', '')}</b>
                <small>Rel-{m.release}</small>
                {cited.has(i) && <em>cited</em>}
              </span>
              <span className="src-sec">§{m.section}</span>
              <span className="src-title">{m.title}</span>
              <span className="src-bar"><i style={{ width: `${norm(s.rerank_score) * 100}%` }} /></span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function Inspector({ sources, index, onClose, onStep }) {
  useEffect(() => {
    const k = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight') onStep(1)
      if (e.key === 'ArrowLeft') onStep(-1)
    }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose, onStep])

  const s = index != null ? sources[index] : null
  const m = s?.metadata
  const cite = m ? `[${m.specification}, Section ${m.section}]` : ''

  return (
    <>
      <div className={`scrim ${s ? 'show' : ''}`} onClick={onClose} />
      <aside className={`drawer glass ${s ? 'show' : ''}`} aria-hidden={!s} aria-label="Source passage">
        {s && (
          <>
            <div className="drawer-head" style={{ '--c': SPEC_COLOR[m.specification] || 'var(--blue)' }}>
              <div>
                <div className="drawer-spec"><i className="src-dot" />{m.specification} · Release {m.release}{m.version ? ` (${m.version})` : ''}</div>
                <h3>§{m.section} {m.title}</h3>
              </div>
              <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="close" size={17} /></button>
            </div>
            <div className="drawer-crumbs">{m.hierarchy}</div>
            <pre className="drawer-text">{s.text}</pre>
            <div className="drawer-foot">
              <div className="scores">
                {s.rerank_score != null && <span>Relevance {s.rerank_score}</span>}
                <span>Found by {s.retrieval_sources?.includes('vector') && s.retrieval_sources?.includes('bm25') ? 'meaning and keywords' : s.retrieval_sources?.includes('bm25') ? 'keywords' : 'meaning'}</span>
              </div>
              <div className="drawer-actions">
                <button className="pill" onClick={() => navigator.clipboard?.writeText(cite)}><Icon name="copy" size={14} />Copy citation</button>
                <button className="icon-btn" onClick={() => onStep(-1)} aria-label="Previous source">←</button>
                <button className="icon-btn" onClick={() => onStep(1)} aria-label="Next source">→</button>
              </div>
            </div>
          </>
        )}
      </aside>
    </>
  )
}
