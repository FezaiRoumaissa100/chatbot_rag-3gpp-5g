import Orb from './Orb.jsx'
import Icon from './icons.jsx'

const PROMPTS = [
  ['layers', 'Architecture', 'What are the main functions of the AMF in the 5G System?'],
  ['signal', 'NAS signalling', 'What does cause #9 mean in 5GMM?'],
  ['split', 'Across two specs', 'Describe the registration procedure and the NAS messages exchanged between the UE and the AMF.'],
  ['shield', 'Security', 'How does 5G AKA work and what is the SUCI?'],
  ['file', 'Between releases', 'Compare the main functions of the AMF between Release 17 and Release 18.'],
  ['globe', 'En français', 'Quelle est la différence entre CM-IDLE et CM-CONNECTED ?'],
]

export default function Hero({ corpus, onPick }) {
  const specs = corpus
    ? [...new Set(corpus.documents.map((d) => d.specification.replace('TS ', '')))]
    : ['23.501', '24.501']
  return (
    <section className="hero">
      <Orb />
      <h1>Ask anything about 5G.</h1>
      <p className="hero-sub">
        Answers come only from the 3GPP specifications ({specs.join(', ')}), and every claim points to its section.
      </p>
      <div className="prompts">
        {PROMPTS.map(([icon, title, q], i) => (
          <button key={q} className="prompt glass glow" style={{ '--d': `${0.55 + i * 0.07}s` }} onClick={() => onPick(q)}>
            <span className="prompt-icon"><Icon name={icon} size={18} /></span>
            <span className="prompt-text">
              <strong>{title}</strong>
              <span>{q}</span>
            </span>
            <span className="prompt-go"><Icon name="arrow" size={16} /></span>
          </button>
        ))}
      </div>
    </section>
  )
}
