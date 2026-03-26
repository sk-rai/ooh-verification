import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../services/api'

function getSessionId(): string {
  let sid = sessionStorage.getItem('tc_sid')
  if (!sid) {
    sid = Math.random().toString(36).slice(2) + Date.now().toString(36)
    sessionStorage.setItem('tc_sid', sid)
  }
  return sid
}

function getUtmParams(): Record<string, string> {
  const params = new URLSearchParams(window.location.search)
  const utm: Record<string, string> = {}
  for (const key of ['utm_source', 'utm_medium', 'utm_campaign']) {
    const val = params.get(key)
    if (val) utm[key] = val
  }
  return utm
}

export default function AnalyticsTracker() {
  const location = useLocation()
  const lastPath = useRef('')

  useEffect(() => {
    // Don't track same page twice in a row
    if (location.pathname === lastPath.current) return
    lastPath.current = location.pathname

    const utm = getUtmParams()
    api.post('/api/analytics/track', {
      page: location.pathname,
      referrer: document.referrer || null,
      session_id: getSessionId(),
      ...utm,
    }).catch(() => {}) // Silent fail — never block UX
  }, [location.pathname])

  return null // Invisible component
}
