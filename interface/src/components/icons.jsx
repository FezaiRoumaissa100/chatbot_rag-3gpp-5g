const P = {
  arrow: <path d="M12 19V5M5 12l7-7 7 7" />,
  stop: <rect x="7" y="7" width="10" height="10" rx="2.5" fill="currentColor" stroke="none" />,
  copy: (<><rect x="9" y="9" width="11" height="11" rx="2.5" /><path d="M5 15V6a2 2 0 0 1 2-2h8" /></>),
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  sun: (<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" /></>),
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  chip: (<><rect x="6" y="6" width="12" height="12" rx="2.5" /><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" /></>),
  cloud: <path d="M7 18a4 4 0 0 1-.6-7.95A6 6 0 0 1 18 9.6 4.2 4.2 0 0 1 17 18H7z" />,
  layers: (<><path d="m12 3 9 5-9 5-9-5 9-5z" /><path d="m3 13 9 5 9-5" /></>),
  shield: <path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3z" />,
  globe: (<><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3.2 3 3.2 15 0 18M12 3c-3.2 3-3.2 15 0 18" /></>),
  split: (<><path d="M12 3v7M12 10 6 15v6M12 10l6 5v6" /></>),
  signal: (<><circle cx="12" cy="12" r="1.8" /><path d="M8 8a5.7 5.7 0 0 0 0 8M16 8a5.7 5.7 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14" /></>),
  mail: (<><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 8 8 5 8-5" /></>),
  file: (<><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" /><path d="M14 3v5h5" /></>),
  warn: <path d="M12 4 2.8 19.5h18.4L12 4zM12 10v4.5M12 17.2v.1" />,
}

export default function Icon({ name, size = 18, stroke = 1.8 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {P[name]}
    </svg>
  )
}
