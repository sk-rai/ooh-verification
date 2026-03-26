const productLinks = [
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Use Cases', href: '#use-cases' },
  { label: 'Features', href: '#features' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'API Documentation', href: 'https://ooh-verification.onrender.com/docs', external: true },
]

const companyLinks = [
  { label: 'About Us', href: '#' },
  { label: 'Contact Us', href: 'mailto:support@lynksavvy.com', external: true },
  { label: 'Careers', href: '#' },
  { label: 'Blog', href: '#' },
]

const legalLinks = [
  { label: 'Privacy Policy', href: '/privacy' },
  { label: 'Terms of Service', href: '/terms' },
  { label: 'Help Center', href: '#' },
  { label: 'System Status', href: '#' },
  { label: 'FAQ', href: '#faq' },
]

export default function Footer() {
  return (
    <footer className="bg-gray-800 text-gray-400">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <p className="text-lg font-bold text-white">TrustCapture</p>
            <p className="mt-2 text-sm leading-relaxed">
              Tamper-proof photo verification for field operations.
            </p>
            <p className="mt-4 text-xs">© 2026 LynkSavvy Technologies.<br />All rights reserved.</p>
          </div>

          {/* Product */}
          <div>
            <p className="text-sm font-semibold text-white mb-3">Product</p>
            <ul className="space-y-2">
              {productLinks.map(l => (
                <li key={l.label}>
                  <a
                    href={l.href}
                    {...(l.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                    className="text-sm hover:text-white transition-colors"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company */}
          <div>
            <p className="text-sm font-semibold text-white mb-3">Company</p>
            <ul className="space-y-2">
              {companyLinks.map(l => (
                <li key={l.label}>
                  <a
                    href={l.href}
                    {...(l.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                    className="text-sm hover:text-white transition-colors"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal */}
          <div>
            <p className="text-sm font-semibold text-white mb-3">Legal & Support</p>
            <ul className="space-y-2">
              {legalLinks.map(l => (
                <li key={l.label}>
                  <a href={l.href} className="text-sm hover:text-white transition-colors">{l.label}</a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-10 pt-6 border-t border-gray-700 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-xs">Built with ❤️ by LynkSavvy Technologies, Lucknow, India</p>
          <div className="flex gap-4">
            <a href="#" className="text-gray-400 hover:text-white transition-colors" aria-label="LinkedIn">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
            </a>
            <a href="#" className="text-gray-400 hover:text-white transition-colors" aria-label="Twitter">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}
