import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface UsageData {
  subscription: { tier: string; status: string; billing_cycle: string; current_period_end: string }
  photos: { used: number; quota: number | string; percentage: number }
  vendors: { used: number; quota: number | string }
  campaigns: { used: number; quota: number | string }
  storage: { used_mb: number; quota_mb: number; percentage: number }
}

interface SubDetails {
  subscription_id: string; tier: string; status: string; billing_cycle: string
  payment_gateway: string | null; amount: number; currency: string
  auto_renew: boolean; current_period_start: string | null; current_period_end: string | null
  photos_quota: number; vendors_quota: number; campaigns_quota: number; storage_quota_mb: number
}

const tierLabels: Record<string, string> = { free: 'Free', pro: 'Pro', enterprise: 'Enterprise' }
const tierColors: Record<string, string> = { free: 'bg-gray-100 text-gray-700', pro: 'bg-blue-100 text-blue-700', enterprise: 'bg-purple-100 text-purple-700' }

function UsageBar({ label, used, quota, unit }: { label: string; used: number; quota: number | string; unit?: string }) {
  const isUnlimited = quota === 'unlimited'
  const pct = isUnlimited ? 5 : (typeof quota === 'number' && quota > 0 ? Math.min(100, (used / quota) * 100) : 0)
  const color = pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-yellow-500' : 'bg-emerald-500'
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-900">{used}{unit ? ` ${unit}` : ''} / {isUnlimited ? '∞' : `${quota}${unit ? ` ${unit}` : ''}`}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function Subscription() {
  const navigate = useNavigate()
  const [usage, setUsage] = useState<UsageData | null>(null)
  const [sub, setSub] = useState<SubDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [cancelLoading, setCancelLoading] = useState(false)
  const [cancelResult, setCancelResult] = useState<any>(null)
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const [upgradeLoading, setUpgradeLoading] = useState(false)
  const [upgradeError, setUpgradeError] = useState('')
  const [selectedTier, setSelectedTier] = useState('')
  const [selectedCycle, setSelectedCycle] = useState('monthly')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [usageRes, subRes] = await Promise.all([
        api.get('/api/subscriptions/usage'),
        api.get('/api/subscriptions/current'),
      ])
      setUsage(usageRes.data)
      setSub(subRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load subscription data')
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async (immediate: boolean) => {
    setCancelLoading(true)
    try {
      const res = await api.post('/api/subscriptions/cancel', { immediate })
      setCancelResult(res.data)
      setShowCancelConfirm(false)
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel subscription')
    } finally {
      setCancelLoading(false)
    }
  }

  const handleUpgrade = async () => {
    setUpgradeLoading(true)
    setUpgradeError('')
    try {
      const res = await api.post('/api/subscriptions/upgrade', {
        tier: selectedTier,
        billing_cycle: selectedCycle,
        payment_gateway: 'razorpay',
      })
      const data = res.data
      // Redirect to payment link
      const paymentUrl = data.checkout?.short_url || data.checkout?.payment_link_url
      if (paymentUrl) {
        window.location.href = paymentUrl
      } else {
        setUpgradeError('Payment gateway not configured yet. Please contact support.')
        setUpgradeLoading(false)
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Upgrade failed'
      if (detail.includes('not configured')) {
        setUpgradeError('Payment gateway is being set up. Please try again later or contact support@lynksavvy.com.')
      } else {
        setUpgradeError(detail)
      }
      setUpgradeLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Navigation />
        <main className="max-w-4xl mx-auto py-8 px-4">
          <p className="text-gray-500">Loading subscription data...</p>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />
      <main className="max-w-4xl mx-auto py-8 px-4 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Subscription & Usage</h1>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{error}</div>
        )}

        {cancelResult && (
          <div className="bg-blue-50 border border-blue-200 px-4 py-3 rounded">
            <p className="text-sm text-blue-800">{cancelResult.message}</p>
            {cancelResult.refund && (
              <p className="text-sm text-blue-700 mt-1">
                Refund: {cancelResult.refund.refund_amount_display} — {cancelResult.refund.note}
              </p>
            )}
          </div>
        )}

        {/* Current Plan */}
        {sub && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Current Plan</h2>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${tierColors[sub.tier] || 'bg-gray-100 text-gray-700'}`}>
                {tierLabels[sub.tier] || sub.tier}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Status</p>
                <p className="font-medium text-gray-900 capitalize">{sub.status}</p>
              </div>
              <div>
                <p className="text-gray-500">Billing Cycle</p>
                <p className="font-medium text-gray-900 capitalize">{sub.billing_cycle || 'Monthly'}</p>
              </div>
              <div>
                <p className="text-gray-500">Amount</p>
                <p className="font-medium text-gray-900">
                  {sub.amount ? `${sub.currency === 'INR' ? '₹' : '$'}${(sub.amount / 100).toFixed(0)}` : 'Free'}
                  {sub.currency === 'INR' && sub.amount > 0 && <span className="text-xs text-gray-400"> + GST</span>}
                </p>
              </div>
              <div>
                <p className="text-gray-500">Period Ends</p>
                <p className="font-medium text-gray-900">
                  {sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : '—'}
                </p>
              </div>
            </div>
          </div>
        )}


        {/* Usage */}
        {usage && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage</h2>
            <div className="space-y-4">
              <UsageBar label="Photos this period" used={usage.photos.used} quota={usage.photos.quota} />
              <UsageBar label="Vendors" used={usage.vendors.used} quota={usage.vendors.quota} />
              <UsageBar label="Campaigns" used={usage.campaigns.used} quota={usage.campaigns.quota} />
              <UsageBar label="Storage" used={usage.storage.used_mb} quota={usage.storage.quota_mb} unit="MB" />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Manage Plan</h2>
          <div className="flex flex-wrap gap-3">
            {sub && sub.tier !== 'enterprise' && (
              <button
                onClick={() => setShowUpgradeModal(true)}
                className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700"
              >
                Upgrade Plan
              </button>
            )}
            {sub && sub.tier !== 'free' && sub.status !== 'cancelled' && (
              <button
                onClick={() => setShowCancelConfirm(true)}
                className="px-4 py-2 border border-red-300 text-red-600 text-sm font-medium rounded-md hover:bg-red-50"
              >
                Cancel Subscription
              </button>
            )}
            <button
              onClick={async () => {
                await api.post('/api/subscriptions/sync-usage')
                await loadData()
              }}
              className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
            >
              Sync Usage
            </button>
          </div>
        </div>

        {/* Upgrade Modal */}
        {showUpgradeModal && sub && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg p-6 max-w-lg w-full space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">Upgrade Your Plan</h3>
              {upgradeError && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">{upgradeError}</div>
              )}
              <div className="space-y-3">
                <p className="text-sm text-gray-600">Select a plan:</p>
                {sub.tier === 'free' && (
                  <button
                    onClick={() => setSelectedTier('pro')}
                    className={`w-full text-left p-4 border rounded-lg ${selectedTier === 'pro' ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'}`}
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-semibold text-gray-900">Pro</p>
                        <p className="text-xs text-gray-500">1,000 photos, 10 vendors, 5 campaigns, 10 GB</p>
                      </div>
                      <p className="font-bold text-gray-900">₹999<span className="text-xs text-gray-400">/mo + GST</span></p>
                    </div>
                  </button>
                )}
                {(sub.tier === 'free' || sub.tier === 'pro') && (
                  <button
                    onClick={() => setSelectedTier('enterprise')}
                    className={`w-full text-left p-4 border rounded-lg ${selectedTier === 'enterprise' ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'}`}
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-semibold text-gray-900">Enterprise</p>
                        <p className="text-xs text-gray-500">Unlimited photos, vendors, campaigns, 100 GB</p>
                      </div>
                      <p className="font-bold text-gray-900">₹4,999<span className="text-xs text-gray-400">/mo + GST</span></p>
                    </div>
                  </button>
                )}
              </div>
              {selectedTier && (
                <div className="space-y-2">
                  <p className="text-sm text-gray-600">Billing cycle:</p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setSelectedCycle('monthly')}
                      className={`flex-1 py-2 text-sm font-medium rounded-md border ${selectedCycle === 'monthly' ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-600'}`}
                    >
                      Monthly
                    </button>
                    <button
                      onClick={() => setSelectedCycle('yearly')}
                      className={`flex-1 py-2 text-sm font-medium rounded-md border ${selectedCycle === 'yearly' ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-600'}`}
                    >
                      Yearly (save 17%)
                    </button>
                  </div>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleUpgrade}
                  disabled={!selectedTier || upgradeLoading}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  {upgradeLoading ? 'Redirecting to payment...' : 'Proceed to Payment'}
                </button>
                <button
                  onClick={() => { setShowUpgradeModal(false); setSelectedTier(''); setUpgradeError(''); }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Cancel Confirmation Modal */}
        {showCancelConfirm && sub && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg p-6 max-w-md w-full space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">Cancel Subscription?</h3>
              <p className="text-sm text-gray-600">
                {sub.billing_cycle === 'yearly'
                  ? 'You can cancel immediately (pro-rata refund for remaining days) or at the end of your billing period.'
                  : 'Your access will continue until the end of your current billing period. No refund for monthly plans.'}
              </p>
              <div className="space-y-2">
                {sub.billing_cycle === 'yearly' && (
                  <button
                    onClick={() => handleCancel(true)}
                    disabled={cancelLoading}
                    className="w-full px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 disabled:opacity-50"
                  >
                    {cancelLoading ? 'Processing...' : 'Cancel Now (Pro-Rata Refund)'}
                  </button>
                )}
                <button
                  onClick={() => handleCancel(false)}
                  disabled={cancelLoading}
                  className="w-full px-4 py-2 border border-red-300 text-red-600 text-sm font-medium rounded-md hover:bg-red-50 disabled:opacity-50"
                >
                  {cancelLoading ? 'Processing...' : 'Cancel at Period End'}
                </button>
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  className="w-full px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
                >
                  Keep My Plan
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Pricing Tiers */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Plans</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { name: 'Free', price: '₹0', features: ['50 photos/mo', '5 vendors', '3 campaigns', '100 MB'] },
              { name: 'Pro', price: '₹999/mo', features: ['1,000 photos/mo', '10 vendors', '5 campaigns', '10 GB'], highlight: true },
              { name: 'Enterprise', price: '₹4,999/mo', features: ['Unlimited photos', 'Unlimited vendors', 'Unlimited campaigns', '100 GB'] },
            ].map(t => (
              <div key={t.name} className={`border rounded-lg p-4 ${t.highlight ? 'border-primary-500 bg-primary-50' : 'border-gray-200'}`}>
                <h3 className="font-semibold text-gray-900">{t.name}</h3>
                <p className="text-lg font-bold text-gray-900 mt-1">{t.price}<span className="text-xs text-gray-400"> + GST</span></p>
                <ul className="mt-3 space-y-1">
                  {t.features.map(f => (
                    <li key={f} className="text-sm text-gray-600 flex items-center gap-1">
                      <span className="text-emerald-500">✓</span> {f}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
