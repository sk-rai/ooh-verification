import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface TopClient {
  client_id: string
  company_name: string
  email: string
  tier: string
  vendors_count: number
  campaigns_count: number
  last_active: string | null
}

interface DashboardData {
  overview: {
    total_tenants: number
    total_clients: number
    total_vendors: number
    total_campaigns: number
    total_assignments: number
    total_photos: number
  }
  clients: {
    total: number
    tier_breakdown: { free: number; pro: number; enterprise: number }
    subscription_breakdown: {
      active: number; cancelled: number
      expired: number; past_due: number
    }
    signups_last_7_days: number
    signups_last_30_days: number
    signup_trend: { date: string; count: number }[]
  }
  usage: {
    heavy_users: TopClient[]
    light_users: TopClient[]
    inactive_users: TopClient[]
    recently_active: TopClient[]
  }
}

type ViewType = 'dashboard' | 'clients' | 'vendors' | 'campaigns'
  | 'heavy' | 'light' | 'inactive' | 'recent'
  | 'free_clients' | 'pro_clients' | 'enterprise_clients'
  | 'active_subs' | 'cancelled_subs' | 'expired_subs' | 'past_due_subs'

const tierColors: Record<string, string> = {
  free: '#94a3b8', pro: '#3b82f6', enterprise: '#a855f7'
}

const cardStyle = (clickable: boolean) => ({
  background: '#1e293b', borderRadius: 10, padding: '20px 24px',
  flex: '1 1 160px', minWidth: 150,
  cursor: clickable ? 'pointer' : 'default',
  transition: 'background 0.15s',
  border: '1px solid transparent',
})

const cardHoverStyle = {
  border: '1px solid #334155',
  background: '#253347',
}

function StatCard({ label, value, sub, onClick }: {
  label: string; value: string | number; sub?: string; onClick?: () => void
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      style={{ ...cardStyle(!!onClick), ...(hovered && onClick ? cardHoverStyle : {}) }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={onClick ? `View ${label} details` : undefined}
    >
      <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 4 }}>{label}</div>
      <div style={{ color: '#f1f5f9', fontSize: 28, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>{sub}</div>}
      {onClick && <div style={{ color: '#3b82f6', fontSize: 11, marginTop: 6 }}>Click to view →</div>}
    </div>
  )
}

function ClientTable({ title, clients, onBack }: {
  title: string; clients: TopClient[]; onBack: () => void
}) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <button onClick={onBack} style={{
          background: '#334155', color: '#cbd5e1', border: 'none',
          padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 13
        }}>← Back</button>
        <h2 style={{ color: '#f1f5f9', fontSize: 18, margin: 0 }}>{title}</h2>
        <span style={{ color: '#64748b', fontSize: 13 }}>({clients.length} clients)</span>
      </div>
      {clients.length === 0 ? (
        <div style={{ background: '#1e293b', borderRadius: 10, padding: 40, textAlign: 'center', color: '#64748b' }}>
          No clients found in this category
        </div>
      ) : (
        <div style={{ background: '#1e293b', borderRadius: 10, padding: 20, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ color: '#94a3b8', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px', borderBottom: '1px solid #334155' }}>#</th>
                <th style={{ padding: '8px 12px', borderBottom: '1px solid #334155' }}>Company</th>
                <th style={{ padding: '8px 12px', borderBottom: '1px solid #334155' }}>Email</th>
                <th style={{ padding: '8px 12px', borderBottom: '1px solid #334155' }}>Tier</th>
                <th style={{ padding: '8px 12px', borderBottom: '1px solid #334155' }}>Vendors</th>
                <th style={{ padding: '8px 12px', borderBottom: '1px solid #334155' }}>Campaigns</th>
                <th style={{ padding: '8px 12px', borderBottom: '1px solid #334155' }}>Last Active</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c, i) => (
                <tr key={c.client_id} style={{
                  color: '#cbd5e1',
                  background: i % 2 === 0 ? 'transparent' : '#1a2332'
                }}>
                  <td style={{ padding: '10px 12px' }}>{i + 1}</td>
                  <td style={{ padding: '10px 12px', fontWeight: 500 }}>{c.company_name}</td>
                  <td style={{ padding: '10px 12px' }}>{c.email}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{
                      background: tierColors[c.tier] || '#475569', color: '#fff',
                      padding: '2px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600
                    }}>
                      {c.tier.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px' }}>{c.vendors_count}</td>
                  <td style={{ padding: '10px 12px' }}>{c.campaigns_count}</td>
                  <td style={{ padding: '10px 12px', color: '#64748b' }}>
                    {c.last_active ? new Date(c.last_active).toLocaleString() : 'Never'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function AdminDashboard() {
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [view, setView] = useState<ViewType>('dashboard')

  useEffect(() => {
    const token = localStorage.getItem('admin_token')
    if (!token) { navigate('/admin/login'); return }
    fetchDashboard(token)
  }, [navigate])

  const fetchDashboard = async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/dashboard`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.status === 401) {
        localStorage.removeItem('admin_token')
        navigate('/admin/login')
        return
      }
      if (!res.ok) throw new Error('Failed to load dashboard')
      setData(await res.json())
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('admin_token')
    navigate('/admin/login')
  }

  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#0f172a', display: 'flex',
      alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
      Loading dashboard...
    </div>
  )

  if (error || !data) return (
    <div style={{ minHeight: '100vh', background: '#0f172a', display: 'flex',
      alignItems: 'center', justifyContent: 'center', color: '#fca5a5' }}>
      {error || 'Failed to load data'}
    </div>
  )

  const { overview: ov, clients: cl, usage } = data
  const goBack = () => setView('dashboard')

  // Filter helpers for tier/status drill-downs
  const allUsers = usage.heavy_users  // heavy_users is sorted by most activity, has all top clients
  const filterByTier = (tier: string) => allUsers.filter(u => u.tier === tier)

  // Render detail view
  if (view !== 'dashboard') {
    const viewConfig: Record<string, { title: string; clients: TopClient[] }> = {
      heavy: { title: 'Heavy Users (most vendors + campaigns)', clients: usage.heavy_users },
      light: { title: 'Light Users (fewest vendors + campaigns)', clients: usage.light_users },
      inactive: { title: 'Inactive Users (no activity in 90+ days)', clients: usage.inactive_users },
      recent: { title: 'Recently Active Users', clients: usage.recently_active },
      free_clients: { title: 'Free Tier Clients', clients: filterByTier('free') },
      pro_clients: { title: 'Pro Tier Clients', clients: filterByTier('pro') },
      enterprise_clients: { title: 'Enterprise Tier Clients', clients: filterByTier('enterprise') },
    }

    const config = viewConfig[view]
    if (config) {
      return (
        <div style={{ minHeight: '100vh', background: '#0f172a', padding: '24px 32px' }}>
          <ClientTable title={config.title} clients={config.clients} onBack={goBack} />
        </div>
      )
    }
  }

  // Main dashboard view
  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', padding: '24px 32px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ color: '#f1f5f9', fontSize: 24, margin: 0 }}>Platform Admin</h1>
          <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
            TrustCapture Super Admin Dashboard
          </p>
        </div>
        <button onClick={handleLogout} style={{
          background: '#334155', color: '#cbd5e1', border: 'none',
          padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontSize: 13
        }}>Logout</button>
      </div>

      {/* Platform Overview - Clickable Cards */}
      <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', marginBottom: 8, letterSpacing: 1 }}>
        Platform Overview
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 28 }}>
        <StatCard label="Tenants" value={ov.total_tenants} />
        <StatCard label="Clients" value={ov.total_clients}
          sub={`${cl.signups_last_7_days} this week`}
          onClick={() => setView('recent')} />
        <StatCard label="Vendors" value={ov.total_vendors} />
        <StatCard label="Campaigns" value={ov.total_campaigns} />
        <StatCard label="Assignments" value={ov.total_assignments} />
        <StatCard label="Photos" value={ov.total_photos} />
      </div>

      {/* Subscription Tiers - Clickable */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 28 }}>
        <div style={{ background: '#1e293b', borderRadius: 10, padding: 20, flex: '1 1 300px' }}>
          <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', marginBottom: 12, letterSpacing: 1 }}>
            Subscription Tiers
          </div>
          <div style={{ display: 'flex', gap: 24 }}>
            {([
              { key: 'free', label: 'FREE', view: 'free_clients' as ViewType },
              { key: 'pro', label: 'PRO', view: 'pro_clients' as ViewType },
              { key: 'enterprise', label: 'ENTERPRISE', view: 'enterprise_clients' as ViewType },
            ]).map(t => (
              <div key={t.key}
                onClick={() => setView(t.view)}
                style={{ textAlign: 'center', cursor: 'pointer', padding: '8px 12px', borderRadius: 8, transition: 'background 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.background = '#334155')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                role="button" tabIndex={0} aria-label={`View ${t.label} clients`}
              >
                <div style={{ color: tierColors[t.key], fontSize: 28, fontWeight: 700 }}>
                  {cl.tier_breakdown[t.key as keyof typeof cl.tier_breakdown]}
                </div>
                <div style={{ color: '#94a3b8', fontSize: 11 }}>{t.label}</div>
                <div style={{ color: '#3b82f6', fontSize: 10, marginTop: 4 }}>View →</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ background: '#1e293b', borderRadius: 10, padding: 20, flex: '1 1 350px' }}>
          <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', marginBottom: 12, letterSpacing: 1 }}>
            Subscription Status
          </div>
          <div style={{ display: 'flex', gap: 20 }}>
            {Object.entries(cl.subscription_breakdown).map(([k, v]) => (
              <div key={k} style={{ textAlign: 'center' }}>
                <div style={{
                  color: k === 'active' ? '#22c55e' : k === 'past_due' ? '#f59e0b' : '#ef4444',
                  fontSize: 28, fontWeight: 700
                }}>{v}</div>
                <div style={{ color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>
                  {k.replace('_', ' ')}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ background: '#1e293b', borderRadius: 10, padding: 20, flex: '1 1 200px' }}>
          <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', marginBottom: 12, letterSpacing: 1 }}>
            Signups
          </div>
          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ color: '#3b82f6', fontSize: 28, fontWeight: 700 }}>{cl.signups_last_7_days}</div>
              <div style={{ color: '#94a3b8', fontSize: 11 }}>Last 7 days</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ color: '#8b5cf6', fontSize: 28, fontWeight: 700 }}>{cl.signups_last_30_days}</div>
              <div style={{ color: '#94a3b8', fontSize: 11 }}>Last 30 days</div>
            </div>
          </div>
        </div>
      </div>

      {/* Signup Trend */}
      {cl.signup_trend.length > 0 && (
        <div style={{ background: '#1e293b', borderRadius: 10, padding: 20, marginBottom: 28 }}>
          <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', marginBottom: 12, letterSpacing: 1 }}>
            Signup Trend (30 days)
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 120, padding: '0 8px' }}>
            {cl.signup_trend.map(d => {
              const max = Math.max(...cl.signup_trend.map(x => x.count), 1)
              const h = Math.max((d.count / max) * 100, 4)
              return (
                <div key={d.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div style={{ color: '#94a3b8', fontSize: 10, marginBottom: 2 }}>{d.count}</div>
                  <div style={{
                    width: '100%', maxWidth: 40, height: h,
                    background: '#3b82f6', borderRadius: 3
                  }} />
                  <div style={{
                    color: '#475569', fontSize: 9, marginTop: 4,
                    transform: 'rotate(-45deg)', whiteSpace: 'nowrap'
                  }}>
                    {d.date.slice(5)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Usage Quick Links */}
      <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', marginBottom: 8, letterSpacing: 1 }}>
        User Activity
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 28 }}>
        <StatCard label="Heavy Users" value={usage.heavy_users.length}
          sub="Most vendors + campaigns" onClick={() => setView('heavy')} />
        <StatCard label="Light Users" value={usage.light_users.length}
          sub="Fewest vendors + campaigns" onClick={() => setView('light')} />
        <StatCard label="Inactive" value={usage.inactive_users.length}
          sub="No activity in 90+ days" onClick={() => setView('inactive')} />
        <StatCard label="Recently Active" value={usage.recently_active.length}
          sub="Most recent activity" onClick={() => setView('recent')} />
      </div>
    </div>
  )
}
