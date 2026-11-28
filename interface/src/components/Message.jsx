import { memo, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Orb from './Orb.jsx'
import Icon from './icons.jsx'
import { SourceStrip } from './Sources.jsx'
import { SPEC_COLOR, findSourceIndex, linkifyCitations, parseCiteHref } from '../lib/cite.js'

const secs = (ms) => (ms == null ? null : `${(ms / 1000).toFixed(1)} s`)

function Routing({ meta }) {
  const r = meta?.routing
  if (!r) return null
  const chips = []
  if (r.target_specs?.length) chips.push(`Searched only ${r.target_specs.join(' and ')}`)
  else if (r.preferred_specs?.length) chips.push(`Prioritised ${r.preferred_specs.join(', ')}`)
  if (r.compare) chips.push(`Releases ${r.releases.join(' and ')} side by side`)
  else if (r.releases?.length) chips.push(`Release ${r.releases.join(', ')}`)
  if (meta.rewritten && meta.language !== 'en') chips.push(`Understood as “${meta.english_query}”`)
  else if (meta.rewritten) chips.push(`Read as “${meta.english_query}”`)
  return (
    <div className="chips">
      {chips.map((c) => <span key={c} className="chip">{c}</span>)}
    </div>
  )
}

function Verify({ citations, refused }) {
  if (refused || !citations || citations.total === 0) return null
  const ok = citations.valid === citations.total
  return (
    <span className={`verify ${ok ? 'ok' : 'bad'}`} title={ok ? 'Every cited section was found in the retrieved passages' : 'Some cited sections are not among the retrieved passages'}>
      <Icon name={ok ? 'check' : 'warn'} size={14} />
      {ok ? `${citations.total} ${citations.total === 1 ? 'citation' : 'citations'} verified` : `${citations.valid} of ${citations.total} citations verified`}
    </span>
  )
}

function AssistantMessage({ msg, activeSource, onOpenSource }) {
  const [copied, setCopied] = useState(false)
  const streaming = msg.status === 'streaming'
  const sources = msg.sources || []

  const cited = useMemo(() => {
    const set = new Set()
    for (const c of msg.done?.citations?.items || []) {
      if (!c.valid) continue
      const i = findSourceIndex(sources, { spec: c.specification, section: c.section, release: c.release })
      if (i >= 0) set.add(i)
    }
    return set
  }, [msg.done, sources])

  const components = useMemo(() => ({
    a({ href, children }) {
      const cite = parseCiteHref(href)
      if (cite) {
        const i = findSourceIndex(sources, cite)
        return (
          <button className="cite" style={{ '--c': SPEC_COLOR[cite.spec] || 'var(--blue)' }}
            disabled={i < 0} onClick={() => i >= 0 && onOpenSource(msg.id, i)}
            title={i < 0 ? 'This section is not among the retrieved passages' : 'Open the source passage'}>
            {children}
          </button>
        )
      }
      return <a href={href} target="_blank" rel="noreferrer">{children}</a>
    },
    table: ({ children }) => <div className="table-wrap"><table>{children}</table></div>,
  }), [sources, onOpenSource, msg.id])

  const stageText = msg.stage === 'analyzing' ? 'Searching the specifications'
    : msg.stage === 'reading' ? `Reading ${sources.length} passage${sources.length === 1 ? '' : 's'}` : ''

  const copy = async () => {
    await navigator.clipboard?.writeText(msg.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }

  return (
    <div className="row assistant">
      <div className="avatar"><Orb size={30} mini busy={streaming} /></div>
      <div className="content">
        {!msg.text && streaming && <div className="stage shimmer" aria-live="polite">{stageText}</div>}

        {msg.status === 'error' ? (
          <div className="error-box"><Icon name="warn" size={16} />{msg.error}</div>
        ) : (
          <div className="md" aria-live="polite">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
              {linkifyCitations(msg.text)}
            </ReactMarkdown>
            {streaming && msg.text && <span className="caret" />}
          </div>
        )}

        {msg.status === 'stopped' && <div className="note">Stopped</div>}

        {sources.length > 0 && (
          <SourceStrip sources={sources} cited={cited} active={activeSource} onOpen={(i) => onOpenSource(msg.id, i)} />
        )}

        {(msg.meta || msg.done) && msg.status !== 'error' && (
          <div className="meta">
            <Routing meta={msg.meta} />
            {msg.status === 'done' && (
              <div className="meta-row">
                <Verify citations={msg.done?.citations} refused={msg.done?.refused} />
                {msg.done?.llm && <span>{msg.done.llm.replace(/^[a-z]+:/, '')}</span>}
                {msg.done?.latency_ms?.total > 0 && (
                  <span title="Query processing, retrieval, generation">
                    {secs(msg.done.latency_ms.retrieval + (msg.done.latency_ms.processing || 0))} to find sources, {secs(msg.done.latency_ms.generation)} to write
                  </span>
                )}
                <button className="icon-btn small" onClick={copy} aria-label="Copy answer">
                  <Icon name={copied ? 'check' : 'copy'} size={15} />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function Message({ msg, activeSource, onOpenSource }) {
  if (msg.role === 'user') {
    return <div className="row user"><div className="bubble">{msg.text}</div></div>
  }
  return <AssistantMessage msg={msg} activeSource={activeSource} onOpenSource={onOpenSource} />
}

export default memo(Message)
