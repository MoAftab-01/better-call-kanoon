import { ArrowUpRight, BookOpen, Info, MessageSquare, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import Brand from './Brand'

const links = [
  { id: 'workspace', label: 'Conversation', Icon: MessageSquare },
  { id: 'sources', label: 'Sources & citations', Icon: BookOpen },
  { id: 'about', label: 'About this workspace', Icon: Info },
]

export default function Sidebar() {
  const [active, setActive] = useState('workspace')

  return (
    <aside className="sidebar" aria-label="Workspace navigation">
      <div className="sidebar-top">
        <Brand />
        <p className="brand-subtitle">Your AI Guide to Indian Law</p>
      </div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        <p className="nav-label">YOUR WORKSPACE</p>
        {links.map(({ id, label, Icon }) => (
          <a
            key={id}
            href={`#${id}`}
            className={`nav-link ${active === id ? 'is-active' : ''}`}
            aria-current={active === id ? 'location' : undefined}
            onClick={() => setActive(id)}
          >
            <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
            <span>{label}</span>
            {active === id && <span className="nav-indicator" aria-hidden="true" />}
          </a>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <div className="sidebar-note">
          <ShieldCheck size={21} strokeWidth={1.5} aria-hidden="true" />
          <h2>A little understanding.<br />A lot more confidence.</h2>
          <p>Taking the first step starts with knowing where you stand.</p>
          <a href="#about">Our approach <ArrowUpRight size={14} aria-hidden="true" /></a>
        </div>
        <div className="sidebar-footer">
          <span className="india-accent" aria-hidden="true"><i /><i /><i /></span>
          <span>Thoughtfully built for India</span>
        </div>
      </div>
    </aside>
  )
}
