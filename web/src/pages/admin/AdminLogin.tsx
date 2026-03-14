import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'

export default function AdminLogin() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Login failed')
      }

      const data = await res.json()
      localStorage.setItem('admin_token', data.access_token)
      navigate('/admin/dashboard')
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#0f172a'
    }}>
      <div style={{
        background: '#1e293b', borderRadius: 12, padding: 40,
        width: 400, boxShadow: '0 4px 24px rgba(0,0,0,0.3)'
      }}>
        <h1 style={{ color: '#f1f5f9', marginBottom: 8, fontSize: 24 }}>
          TrustCapture Admin
        </h1>
        <p style={{ color: '#94a3b8', marginBottom: 24, fontSize: 14 }}>
          Platform administration portal
        </p>

        {error && (
          <div style={{
            background: '#7f1d1d', color: '#fca5a5', padding: '8px 12px',
            borderRadius: 6, marginBottom: 16, fontSize: 14
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: '#cbd5e1', fontSize: 14, display: 'block', marginBottom: 4 }}>
              Email
            </label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              required placeholder="admin@trustcapture.com"
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 6,
                border: '1px solid #334155', background: '#0f172a',
                color: '#f1f5f9', fontSize: 14, boxSizing: 'border-box'
              }}
            />
          </div>
          <div style={{ marginBottom: 24 }}>
            <label style={{ color: '#cbd5e1', fontSize: 14, display: 'block', marginBottom: 4 }}>
              Password
            </label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              required
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 6,
                border: '1px solid #334155', background: '#0f172a',
                color: '#f1f5f9', fontSize: 14, boxSizing: 'border-box'
              }}
            />
          </div>
          <button
            type="submit" disabled={loading}
            style={{
              width: '100%', padding: '10px 0', borderRadius: 6,
              background: loading ? '#475569' : '#3b82f6', color: '#fff',
              border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer'
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
