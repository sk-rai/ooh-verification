import { useState, useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import api from '../services/api'

interface QuickStats {
  photos: { used: number; quota: number | string }
  vendors: { used: number; quota: number | string }
  campaigns: { used: number; quota: number | string }
  storage: { used_mb: number; quota_mb: number }
  subscription?: { tier: string; status: string; current_period_end: string }
}

export default function Navigation() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [profileOpen, setProfileOpen] = useState(false)
  const [stats, setStats] = useState<QuickStats | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(path + '/')

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setProfileOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Fetch stats when dropdown opens
  useEffect(() => {
    if (profileOpen && !stats) {
      api.get('/api/subscriptions/usage').then(r => setStats(r.data)).catch(() => {})
    }
  }, [profileOpen])

  const tierColors: Record<string, string> = {
    free: 'bg-gray-100 text-gray-700',
    pro: 'bg-blue-100 text-blue-700',
    enterprise: 'bg-purple-100 text-purple-700',
  }


  const navLinks = [
    { to: '/dashboard', label: 'Dashboard', exact: true },
    { to: '/campaigns', label: 'Campaigns' },
    { to: '/vendors', label: 'Vendors' },
    { to: '/photos', label: 'Photos' },
    { to: '/reports', label: 'Reports' },
    { to: '/map', label: 'Map' },
  ]

  const initials = user?.company_name
    ? user.company_name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.slice(0, 2).toUpperCase() || '?'

  return (
    <nav className="bg-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/dashboard" className="text-xl font-bold text-gray-900">TrustCapture</Link>
            <div className="hidden md:flex space-x-1">
              {navLinks.map(l => (
                <Link
                  key={l.to}
                  to={l.to}
                  className={`px-3 py-2 rounded-md text-sm font-medium ${
                    l.exact
                      ? (location.pathname === l.to ? 'text-gray-900 bg-gray-100' : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50')
                      : (isActive(l.to) ? 'text-gray-900 bg-gray-100' : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50')
                  }`}
                >
                  {l.label}
                </Link>
              ))}
            </div>
          </div>

          {/* Profile dropdown */}
          <div className="flex items-center" ref={dropdownRef}>
            <button
              onClick={() => setProfileOpen(!profileOpen)}
              className="flex items-center space-x-2 px-2 py-1 rounded-md hover:bg-gray-50 transition-colors"
              aria-label="Profile menu"
            >
              <div className="w-8 h-8 rounded-full bg-primary-600 text-white flex items-center justify-center text-xs font-semibold">
                {initials}
              </div>
              <svg className={`w-4 h-4 text-gray-400 transition-transform ${profileOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {profileOpen && (
              <div className="absolute right-4 top-14 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50 overflow-hidden">
                {/* Header */}
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-semibold text-gray-900">{user?.company_name}</p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                  <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${tierColors[user?.subscription_tier || 'free']}`}>
                    {(user?.subscription_tier || 'free').toUpperCase()} Plan
                  </span>
                </div>


                {/* Quick Stats */}
                {stats ? (
                  <div className="px-4 py-3 space-y-2 border-b border-gray-100">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Usage</p>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="text-xs">
                        <span className="text-gray-500">Campaigns</span>
                        <p className="font-semibold text-gray-900">{stats.campaigns.used} / {stats.campaigns.quota === 'unlimited' ? '∞' : stats.campaigns.quota}</p>
                      </div>
                      <div className="text-xs">
                        <span className="text-gray-500">Vendors</span>
                        <p className="font-semibold text-gray-900">{stats.vendors.used} / {stats.vendors.quota === 'unlimited' ? '∞' : stats.vendors.quota}</p>
                      </div>
                      <div className="text-xs">
                        <span className="text-gray-500">Photos</span>
                        <p className="font-semibold text-gray-900">{stats.photos.used} / {stats.photos.quota === 'unlimited' ? '∞' : stats.photos.quota}</p>
                      </div>
                      <div className="text-xs">
                        <span className="text-gray-500">Storage</span>
                        <p className="font-semibold text-gray-900">{stats.storage.used_mb} / {stats.storage.quota_mb} MB</p>
                      </div>
                    </div>
                    {stats.subscription?.current_period_end && (
                      <p className="text-xs text-gray-400">
                        Period ends: {new Date(stats.subscription.current_period_end).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="px-4 py-3 border-b border-gray-100">
                    <p className="text-xs text-gray-400">Loading usage...</p>
                  </div>
                )}

                {/* Links */}
                <div className="py-1">
                  <Link
                    to="/subscription"
                    onClick={() => setProfileOpen(false)}
                    className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    Manage Subscription
                  </Link>
                  <Link
                    to="/dashboard"
                    onClick={() => setProfileOpen(false)}
                    className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    Dashboard
                  </Link>
                </div>

                {/* Logout */}
                <div className="border-t border-gray-100 py-1">
                  <button
                    onClick={() => { setProfileOpen(false); logout(); }}
                    className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
