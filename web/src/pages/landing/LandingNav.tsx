import { useState } from 'react'
import { Link } from 'react-router-dom'

export default function LandingNav() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <a href="/" className="text-xl font-bold text-gray-900">TrustCapture</a>

          <div className="hidden md:flex items-center space-x-4">
            <Link to="/login" className="text-sm font-medium text-primary-600 hover:text-primary-700">Login</Link>
            <Link to="/register" className="text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 px-4 py-2 rounded-md transition-colors">
              Start Free Trial
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileOpen
                ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              }
            </svg>
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="md:hidden bg-white border-t border-gray-100 px-4 py-3 space-y-2">
          <Link to="/login" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-primary-600 py-2">Login</Link>
          <Link to="/register" onClick={() => setMobileOpen(false)} className="block text-sm font-medium text-white bg-primary-600 text-center px-4 py-2 rounded-md">
            Start Free Trial
          </Link>
        </div>
      )}
    </nav>
  )
}
