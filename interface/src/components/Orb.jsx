export default function Orb({ size = 190, busy = false, mini = false }) {
  return (
    <div className={`orb ${busy ? 'busy' : ''} ${mini ? 'mini' : ''}`} style={{ '--s': `${size}px` }} aria-hidden="true">
      {!mini && (<><span className="ripple r1" /><span className="ripple r2" /><span className="ripple r3" /></>)}
      <span className="orb-glow" />
      <span className="orb-core" />
    </div>
  )
}
