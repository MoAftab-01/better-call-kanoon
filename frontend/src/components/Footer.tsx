/**
 * Site footer: product name, description and the standing "not a lawyer" line.
 *
 * The footer note is deliberately not dismissible. The banner up top can be
 * closed for the session; this one always stays.
 */
import type { Strings } from '../i18n'

interface FooterProps {
  appName: string
  description: string
  strings: Strings
}

export function Footer({ appName, description, strings }: FooterProps) {
  return (
    <footer className="site-footer">
      <div className="shell footer-inner">
        <p className="footer-line">
          {appName} · {description}
        </p>
        <p className="footer-line footer-meta">{strings.footerNote}</p>
      </div>
    </footer>
  )
}
