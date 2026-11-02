import { Scale } from 'lucide-react'

export default function Brand() {
  return (
    <a className="brand" href="#main-content" aria-label="Better Call Kanoon home">
      <span className="brand-mark"><Scale size={25} strokeWidth={1.5} aria-hidden="true" /></span>
      <span className="brand-name">Better Call <strong>Kanoon<span>.</span></strong></span>
    </a>
  )
}
