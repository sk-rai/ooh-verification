import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import Navigation from '../../components/Navigation'
import api from '../../services/api'
import 'leaflet/dist/leaflet.css'

interface PhotoLocation {
  photo_id: string
  campaign_name: string
  campaign_code: string
  vendor_name: string
  latitude: number
  longitude: number
  verification_status: string
  confidence: number
  flags: string[]
  captured_at: string
  thumbnail_url?: string
  photo_url?: string
}

export default function MapView() {
  const [photos, setPhotos] = useState<PhotoLocation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedPhoto, setSelectedPhoto] = useState<PhotoLocation | null>(null)
  const [filters, setFilters] = useState({ campaign: '', status: '' })
  const [campaigns, setCampaigns] = useState<Array<{ campaign_id: string; name: string }>>([])

  useEffect(() => { fetchData() }, [])

  const fetchData = async () => {
    try {
      const [photosRes, campaignsRes] = await Promise.all([
        api.get('/api/photos/locations'),
        api.get('/api/campaigns'),
      ])
      const locData = photosRes.data
      const photoArr = Array.isArray(locData) ? locData : (locData?.features || []).map((f: any) => ({
        photo_id: f.properties?.photo_id || '',
        latitude: f.geometry?.coordinates?.[1] || 0,
        longitude: f.geometry?.coordinates?.[0] || 0,
        verification_status: f.properties?.status || 'pending',
        confidence: f.properties?.confidence || 0,
        flags: f.properties?.flags || [],
        campaign_name: f.properties?.campaign_name || '',
        campaign_code: f.properties?.campaign_code || '',
        vendor_name: f.properties?.vendor_name || '',
        photo_url: f.properties?.photo_url || '',
        thumbnail_url: f.properties?.thumbnail_url || '',
        captured_at: f.properties?.captured_at || '',
      }))
      setPhotos(photoArr)
      setCampaigns(Array.isArray(campaignsRes.data) ? campaignsRes.data : (campaignsRes.data?.campaigns || []))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load map data')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'verified': return '#22c55e'
      case 'rejected': case 'failed': return '#ef4444'
      case 'pending': return '#eab308'
      default: return '#6b7280'
    }
  }

  const getStatusDotClass = (status: string) => {
    switch (status) {
      case 'verified': return 'bg-green-500'
      case 'rejected': case 'failed': return 'bg-red-500'
      case 'pending': return 'bg-yellow-500'
      default: return 'bg-gray-500'
    }
  }

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'N/A'
    try {
      const d = new Date(dateStr)
      if (isNaN(d.getTime())) return 'N/A'
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch { return 'N/A' }
  }

  const filteredPhotos = photos.filter(photo => {
    if (filters.campaign && photo.campaign_name !== filters.campaign) return false
    if (filters.status && photo.verification_status !== filters.status) return false
    return true
  })

  const center: [number, number] = filteredPhotos.length > 0
    ? [
        filteredPhotos.reduce((s, p) => s + p.latitude, 0) / filteredPhotos.length,
        filteredPhotos.reduce((s, p) => s + p.longitude, 0) / filteredPhotos.length,
      ]
    : [20, 0]

  const exportGeoJSON = async () => {
    try {
      const response = await api.get('/api/photos/locations')
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `trustcapture-locations-${Date.now()}.geojson`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch { alert('Failed to export GeoJSON') }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Map View</h2>
            <p className="text-gray-600 mt-1">Visualize photo locations on a map</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{error}</div>
          )}

          {/* Filters */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-1">Campaign</label>
                <select value={filters.campaign} onChange={(e) => setFilters({ ...filters, campaign: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                  <option value="">All Campaigns</option>
                  {campaigns.map((c) => (
                    <option key={c.campaign_id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                  <option value="">All Status</option>
                  <option value="verified">Verified</option>
                  <option value="pending">Pending</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
              <button onClick={exportGeoJSON}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center">
                <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Export GeoJSON
              </button>
            </div>
            <div className="mt-4 text-sm text-gray-600">
              Showing {filteredPhotos.length} of {photos.length} locations
            </div>
          </div>

          {loading ? (
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">Loading map data...</p>
            </div>
          ) : filteredPhotos.length === 0 ? (
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">No photo locations available.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Leaflet Map */}
              <div className="lg:col-span-2">
                <div className="bg-white shadow rounded-lg overflow-hidden">
                  <MapContainer center={center} zoom={13} style={{ height: '600px', width: '100%' }} scrollWheelZoom={true}>
                    <TileLayer
                      attribution={'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    {filteredPhotos.map((photo) => (
                      <CircleMarker
                        key={photo.photo_id}
                        center={[photo.latitude, photo.longitude]}
                        radius={10}
                        pathOptions={{ color: getStatusColor(photo.verification_status), fillColor: getStatusColor(photo.verification_status), fillOpacity: 0.7 }}
                        eventHandlers={{ click: () => setSelectedPhoto(photo) }}
                      >
                        <Popup>
                          <div className="text-sm">
                            <p className="font-semibold">{photo.campaign_name || 'Unknown Campaign'}</p>
                            <p className="text-gray-600">{photo.vendor_name || 'Unknown Vendor'}</p>
                            <p>Status: <span className="font-medium">{photo.verification_status}</span></p>
                            <p>Confidence: {((photo.confidence || 0) * 100).toFixed(0)}%</p>
                            {photo.flags && photo.flags.length > 0 && (
                              <div className="mt-1">
                                <p className="font-medium text-red-600">Rejection Reasons:</p>
                                <ul className="list-disc list-inside text-xs">
                                  {photo.flags.map((flag: string, i: number) => <li key={i}>{flag}</li>)}
                                </ul>
                              </div>
                            )}
                            <p className="text-xs text-gray-400 mt-1">{formatDate(photo.captured_at)}</p>
                            {photo.thumbnail_url && (
                              <img src={photo.thumbnail_url} alt="Photo" className="mt-2 w-32 h-24 object-cover rounded" />
                            )}
                          </div>
                        </Popup>
                      </CircleMarker>
                    ))}
                  </MapContainer>
                </div>
              </div>

              {/* Location List */}
              <div className="lg:col-span-1">
                <div className="bg-white shadow rounded-lg p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Photo Locations</h3>
                  <div className="space-y-3 max-h-[550px] overflow-y-auto">
                    {filteredPhotos.map((photo) => (
                      <button key={photo.photo_id} onClick={() => setSelectedPhoto(photo)}
                        className={`w-full text-left p-3 rounded-lg border transition ${
                          selectedPhoto?.photo_id === photo.photo_id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                        }`}>
                        <div className="flex items-start space-x-3">
                          <div className={`w-3 h-3 rounded-full mt-1 ${getStatusDotClass(photo.verification_status)}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">{photo.campaign_name || 'Unknown'}</p>
                            <p className="text-xs text-gray-500 truncate">{photo.vendor_name || 'Unknown'}</p>
                            <p className="text-xs text-gray-400 mt-1 font-mono">
                              {(photo.latitude ?? 0).toFixed(6)}, {(photo.longitude ?? 0).toFixed(6)}
                            </p>
                            <p className="text-xs text-gray-400">{formatDate(photo.captured_at)}</p>
                            {photo.flags && photo.flags.length > 0 && (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {photo.flags.map((flag: string, i: number) => (
                                  <span key={i} className="inline-block px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded">{flag}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Legend */}
          <div className="mt-6 bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-medium text-gray-900 mb-3">Legend</h3>
            <div className="flex flex-wrap gap-4">
              <div className="flex items-center">
                <div className="w-4 h-4 rounded-full bg-green-500 mr-2" />
                <span className="text-sm text-gray-600">Verified</span>
              </div>
              <div className="flex items-center">
                <div className="w-4 h-4 rounded-full bg-yellow-500 mr-2" />
                <span className="text-sm text-gray-600">Pending</span>
              </div>
              <div className="flex items-center">
                <div className="w-4 h-4 rounded-full bg-red-500 mr-2" />
                <span className="text-sm text-gray-600">Failed / Rejected</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
