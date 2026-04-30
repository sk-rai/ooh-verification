import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface CampaignData {
  campaign_id: string
  name: string
  campaign_code: string
  campaign_type: string
  status: string
  start_date: string
  end_date: string
  location_profile?: {
    expected_latitude: number
    expected_longitude: number
    tolerance_meters: number
    resolved_address?: string
    delivery_window_start?: string
    delivery_window_end?: string
  }
}

export default function EditCampaign() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [campaign, setCampaign] = useState<CampaignData | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    status: '',
    end_date: '',
  })

  useEffect(() => {
    fetchCampaign()
  }, [id])

  const fetchCampaign = async () => {
    try {
      const res = await api.get(`/api/campaigns/${id}`)
      const c = res.data
      setCampaign(c)
      setFormData({
        name: c.name || '',
        status: c.status || 'active',
        end_date: c.end_date ? c.end_date.split('T')[0] : '',
      })
    } catch (err) {
      setError('Failed to load campaign')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')

    try {
      const updateData: any = {}
      if (formData.name !== campaign?.name) updateData.name = formData.name
      if (formData.status !== campaign?.status) updateData.status = formData.status
      if (formData.end_date) {
        const newEnd = new Date(formData.end_date).toISOString()
        if (newEnd !== campaign?.end_date) updateData.end_date = newEnd
      }

      if (Object.keys(updateData).length === 0) {
        setError('No changes to save')
        setSaving(false)
        return
      }

      await api.patch(`/api/campaigns/${id}`, updateData)
      setSuccess('Campaign updated successfully')
      setTimeout(() => navigate(`/campaigns/${id}`), 1500)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to update campaign')
    } finally {
      setSaving(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Navigation />
        <main className="max-w-4xl mx-auto py-6 px-4">
          <p className="text-gray-500">Loading campaign...</p>
        </main>
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Navigation />
        <main className="max-w-4xl mx-auto py-6 px-4">
          <p className="text-red-500">Campaign not found</p>
          <button onClick={() => navigate('/campaigns')} className="mt-4 text-blue-600 hover:underline">
            Back to Campaigns
          </button>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Edit Campaign</h2>
              <p className="text-gray-600 mt-1">
                {campaign.name} ({campaign.campaign_code})
              </p>
            </div>
            <button
              onClick={() => navigate(`/campaigns/${id}`)}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {success && (
            <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Editable Fields */}
            <div className="bg-white shadow rounded-lg p-6 space-y-6">
              <h3 className="text-lg font-medium text-gray-900">Campaign Details</h3>

              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                  Campaign Name
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>

              <div>
                <label htmlFor="status" className="block text-sm font-medium text-gray-700">
                  Status
                </label>
                <select
                  id="status"
                  name="status"
                  value={formData.status}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="completed">Completed</option>
                </select>
              </div>

              <div>
                <label htmlFor="end_date" className="block text-sm font-medium text-gray-700">
                  End Date
                </label>
                <input
                  type="date"
                  id="end_date"
                  name="end_date"
                  value={formData.end_date}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Read-only Info */}
            <div className="bg-white shadow rounded-lg p-6 space-y-4">
              <h3 className="text-lg font-medium text-gray-900">Campaign Info (Read-only)</h3>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Campaign Code:</span>
                  <p className="font-medium">{campaign.campaign_code}</p>
                </div>
                <div>
                  <span className="text-gray-500">Type:</span>
                  <p className="font-medium capitalize">{campaign.campaign_type}</p>
                </div>
                <div>
                  <span className="text-gray-500">Start Date:</span>
                  <p className="font-medium">{campaign.start_date ? new Date(campaign.start_date).toLocaleDateString() : 'N/A'}</p>
                </div>
                {campaign.location_profile && (
                  <>
                    <div>
                      <span className="text-gray-500">Target Location:</span>
                      <p className="font-medium">
                        {campaign.location_profile.resolved_address || 
                         `${campaign.location_profile.expected_latitude?.toFixed(6)}, ${campaign.location_profile.expected_longitude?.toFixed(6)}`}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-500">Tolerance:</span>
                      <p className="font-medium">{campaign.location_profile.tolerance_meters}m</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <button
                type="button"
                onClick={() => navigate(`/campaigns/${id}`)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
