import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface LocationEntry {
  id: string
  address: string
  latitude: string
  longitude: string
  radius_meters: string
}

export default function EditCampaign() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [geocoding, setGeocoding] = useState(false)
  const [geocodeMessage, setGeocodeMessage] = useState('')

  const [formData, setFormData] = useState({ name: '', status: '', end_date: '' })
  const [campaignInfo, setCampaignInfo] = useState<any>(null)
  const [locations, setLocations] = useState<LocationEntry[]>([])

  useEffect(() => { fetchCampaign() }, [id])

  const fetchCampaign = async () => {
    try {
      const res = await api.get(`/api/campaigns/${id}`)
      const c = res.data
      setCampaignInfo(c)
      setFormData({
        name: c.name || '',
        status: c.status || 'active',
        end_date: c.end_date ? c.end_date.split('T')[0] : '',
      })
      const lps = Array.isArray(c.location_profile) ? c.location_profile : (c.location_profile ? [c.location_profile] : [])
      if (lps.length > 0) {
        setLocations(lps.map((lp: any, i: number) => ({
          id: String(i + 1),
          address: lp.resolved_address || '',
          latitude: lp.expected_latitude ? String(lp.expected_latitude) : '',
          longitude: lp.expected_longitude ? String(lp.expected_longitude) : '',
          radius_meters: lp.tolerance_meters ? String(lp.tolerance_meters) : '100',
        })))
      } else {
        setLocations([{ id: '1', address: '', latitude: '', longitude: '', radius_meters: '100' }])
      }
    } catch (err) {
      setError('Failed to load campaign')
    } finally {
      setLoading(false)
    }
  }

  const geocodeAddress = async (locationId: string) => {
    const loc = locations.find(l => l.id === locationId)
    if (!loc || !loc.address.trim()) return
    setGeocoding(true); setGeocodeMessage('')
    try {
      const res = await api.post('/api/campaigns/geocode', { address: loc.address })
      if (res.data?.latitude && res.data?.longitude) {
        updateLocation(locationId, 'latitude', String(res.data.latitude))
        updateLocation(locationId, 'longitude', String(res.data.longitude))
        setGeocodeMessage(`Resolved: ${res.data.formatted_address}`)
      }
    } catch { setGeocodeMessage('Could not resolve address') }
    finally { setGeocoding(false) }
  }

  const addLocation = () => {
    setLocations([...locations, { id: Date.now().toString(), address: '', latitude: '', longitude: '', radius_meters: '100' }])
  }
  const removeLocation = (lid: string) => {
    if (locations.length > 1) setLocations(locations.filter(l => l.id !== lid))
  }
  const updateLocation = (lid: string, field: keyof LocationEntry, value: string) => {
    setLocations(prev => prev.map(l => l.id === lid ? { ...l, [field]: value } : l))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setError(''); setSuccess('')
    try {
      const updateData: any = {}
      if (formData.name !== campaignInfo?.name) updateData.name = formData.name
      if (formData.status !== campaignInfo?.status) updateData.status = formData.status
      if (formData.end_date) {
        const newEnd = new Date(formData.end_date).toISOString()
        if (newEnd !== campaignInfo?.end_date) updateData.end_date = newEnd
      }
      updateData.locations = locations
        .filter(loc => loc.address.trim() || (loc.latitude && loc.longitude))
        .map(loc => ({
          expected_latitude: loc.latitude ? parseFloat(loc.latitude) : undefined,
          expected_longitude: loc.longitude ? parseFloat(loc.longitude) : undefined,
          tolerance_meters: parseFloat(loc.radius_meters) || 100,
          address: loc.address.trim() || undefined,
        }))

      await api.patch(`/api/campaigns/${id}`, updateData)
      setSuccess('Campaign updated successfully')
      setTimeout(() => navigate(`/campaigns/${id}`), 1500)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail) || 'Failed to update')
    } finally { setSaving(false) }
  }

  if (loading) return <div className="min-h-screen bg-gray-100"><Navigation /><main className="max-w-4xl mx-auto py-6 px-4"><p className="text-gray-500">Loading...</p></main></div>
  if (!campaignInfo) return <div className="min-h-screen bg-gray-100"><Navigation /><main className="max-w-4xl mx-auto py-6 px-4"><p className="text-red-500">Campaign not found</p></main></div>

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />
      <main className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Edit Campaign</h2>
              <p className="text-gray-600 mt-1">{campaignInfo.name} ({campaignInfo.campaign_code})</p>
            </div>
            <button onClick={() => navigate(`/campaigns/${id}`)} className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">Cancel</button>
          </div>

          {error && <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{error}</div>}
          {success && <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">{success}</div>}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="bg-white shadow rounded-lg p-6 space-y-6">
              <h3 className="text-lg font-medium text-gray-900">Campaign Details</h3>
              <div>
                <label className="block text-sm font-medium text-gray-700">Campaign Name</label>
                <input type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Status</label>
                <select value={formData.status} onChange={e => setFormData({...formData, status: e.target.value})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                  <option value="active">Active</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">End Date</label>
                <input type="date" value={formData.end_date} onChange={e => setFormData({...formData, end_date: e.target.value})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" />
              </div>
            </div>

            <div className="bg-white shadow rounded-lg p-6 space-y-6">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-medium text-gray-900">Target Locations</h3>
                <button type="button" onClick={addLocation}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
                  + Add Location
                </button>
              </div>

              {locations.map((loc, index) => (
                <div key={loc.id} className="border border-gray-200 rounded-lg p-4 space-y-3">
                  <div className="flex justify-between items-start">
                    <h4 className="text-sm font-medium text-gray-900">Location {index + 1}</h4>
                    {locations.length > 1 && (
                      <button type="button" onClick={() => removeLocation(loc.id)} className="text-red-600 hover:text-red-800 text-sm">Remove</button>
                    )}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Address</label>
                    <input type="text" value={loc.address} onChange={e => updateLocation(loc.id, 'address', e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" placeholder="Street address" />
                    <button type="button" onClick={() => geocodeAddress(loc.id)} disabled={geocoding || !loc.address.trim()}
                      className="mt-1 px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50">
                      {geocoding ? 'Resolving...' : 'Resolve to Coordinates'}
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Latitude</label>
                      <input type="number" step="0.0000001" value={loc.latitude} onChange={e => updateLocation(loc.id, 'latitude', e.target.value)}
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Longitude</label>
                      <input type="number" step="0.0000001" value={loc.longitude} onChange={e => updateLocation(loc.id, 'longitude', e.target.value)}
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Radius (m)</label>
                      <input type="number" min="10" max="5000" value={loc.radius_meters} onChange={e => updateLocation(loc.id, 'radius_meters', e.target.value)}
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" />
                    </div>
                  </div>
                  {geocodeMessage && <p className="text-xs text-blue-600">{geocodeMessage}</p>}
                </div>
              ))}

              <p className="text-xs text-gray-500">Free: up to 5 locations | Pro: up to 500 | Enterprise: unlimited</p>
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <button type="button" onClick={() => navigate(`/campaigns/${id}`)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">Cancel</button>
              <button type="submit" disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50">
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
