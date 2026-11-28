// Turns "[TS 23.501, Section 6.2.1]" into clickable markdown links, and maps them back to sources.
const CITE_RE =
  /\[\s*TS\s*(\d{2}\.\d{3})(?:\s*\(?\s*Rel(?:ease)?[-\s]*(\d{2})\)?)?\s*,\s*(?:Section|Sec\.?|Clause)\s*(Annex\s+[A-Z](?:\.\w+)*|\d+(?:\.\w+)*|[A-Z](?:\.\w+)+)\s*\]/gi

export function linkifyCitations(text) {
  return (text || '').replace(CITE_RE, (_m, spec, rel, sec) => {
    const label = `${spec} §${sec}${rel ? ` · R${rel}` : ''}`
    return `[${label}](#cite/${spec}/${encodeURIComponent(sec)}/${rel || ''})`
  })
}

export function parseCiteHref(href) {
  const m = /^#cite\/([\d.]+)\/([^/]+)\/(\d*)$/.exec(href || '')
  return m ? { spec: `TS ${m[1]}`, section: decodeURIComponent(m[2]), release: m[3] || null } : null
}

const secMatch = (a, b) => a === b || a.startsWith(b + '.') || b.startsWith(a + '.')

export function findSourceIndex(sources, cite) {
  return sources.findIndex((s) => {
    const m = s.metadata
    return (
      m.specification === cite.spec &&
      (!cite.release || String(m.release) === cite.release) &&
      secMatch(String(m.section), cite.section)
    )
  })
}

export const SPEC_COLOR = {
  'TS 23.501': 'var(--blue)',
  'TS 24.501': 'var(--violet)',
  'TS 23.502': 'var(--mint)',
  'TS 33.501': 'var(--amber)',
}
