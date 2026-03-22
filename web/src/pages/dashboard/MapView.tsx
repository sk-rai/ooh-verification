import { useState, useEffect, useRef } from 'react'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface PhotoLocation {
  photo_id: string
  campaign_name: string
  vendor_name: string
  latitude: number
  longitude: number
  verification_status: string
  confidence_score: number
  captured_at: string
  thumbnail_url?: string
}

export default function MapView() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const [photos, setPhotos] = useState<PhotoLocation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedPhoto, setSelectedPhoto] = useState<PhotoLocation | null>(null)
  const [filters, setFilters] = useState({
    campaign: '',
    status: '',
  })
  const [campaigns, setCampaigns] = useState<Array<{ campaign_id: string; name: string }>>([])

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    if (photos.length > 0 && mapContainer.current && !map.current) {
      initializeMap()
    }
  }, [photos])

  const fetchData = async () => {
    try {
      const [photosRes, campaignsRes] = await Promise.all([
        api.get('/api/photos/locations'),
        api.get('/api/campaigns'),
      ])

      setPhotos(photosRes.data)
      setCampaigns(campaignsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load map data')
    } finally {
      setLoading(false)
    }
  }

  const initializeMap = () => {
    // Simple map implementation without Mapbox (fallback)
    // In production, you would use Mapbox GL JS here
    console.log('Map would be initialized here with Mapbox GL JS')
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-500'
      case 'failed':
        return 'bg-red-500'
      case 'pending':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const filteredPhotos = photos.filter(photo => {
    if (filters.campaign && photo.campaign_name !== filters.campaign) return false
    if (filters.status && photo.verification_status !== filters.status) return false
    return true
  })

  const exportGeoJSON = async () => {
    try {
      const response = await api.get('/api/reports/export/geojson', {
        responseType: 'blob',
        params: {
          campaign_id: filters.campaign,
          status: filters.status,
        },
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `trustcapture-locations-${Date.now()}.geojson`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Failed to export GeoJSON')
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Header */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Map View</h2>
            <p className="text-gray-600 mt-1">Visualize photo locations on a map</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Filters & Export */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-1">Campaign</label>
                <select
                  value={filters.campaign}
                  onChange={(e) => setFilters({ ...filters, campaign: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">All Campaigns</option>
                  {campaigns.map((c) => (
                    <option key={c.campaign_id} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">All Status</option>
                  <option value="verified">Verified</option>
                  <option value="pending">Pending</option>
                  <option value="failed">Failed</option>
                </select>
              </div>
              <button
                onClick={exportGeoJSON}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center"
              >
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
              <p className="text-gray-500 text-center py-8">
                No photo locations available.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Map Container */}
              <div className="lg:col-span-2">
                <div className="bg-white shadow rounded-lg overflow-hidden">
                  <div
                    ref={mapContainer}
                    className="w-full h-[600px] bg-gray-200 flex items-center justify-center"
                  >
                    <div className="text-center">
                      <svg className="mx-auto h-16 w-16 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                      </svg>
                      <p className="text-gray-600 font-medium">Interactive Map</p>
                      <p className="text-sm text-gray-500 mt-2">
                        Mapbox integration coming soon
                      </p>
                      <p className="text-xs text-gray-400 mt-4">
                        Will display photo locations with clustering and popups
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Location List */}
              <div className="lg:col-span-1">
                <div className="bg-white shadow rounded-lg p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Photo Locations</h3>
                  <div className="space-y-3 max-h-[550px] overflow-y-auto">
                    {filteredPhotos.map((photo) => (
                      <button
                        key={photo.photo_id}
                        onClick={() => setSelectedPhoto(photo)}
                        className={`w-full text-left p-3 rounded-lg border transition ${
                          selectedPhoto?.photo_id === photo.photo_id
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-start space-x-3">
                          <div className={`w-3 h-3 rounded-full mt-1 ${getStatusColor(photo.verification_status)}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {photo.campaign_name}
                            </p>
                            <p className="text-xs text-gray-500 truncate">
                              {photo.vendor_name}
                            </p>
                            <p className="text-xs text-gray-400 mt-1 font-mono">
                              {photo.latitude.toFixed(6)}, {photo.longitude.toFixed(6)}
                            </p>
                            <p className="text-xs text-gray-400">
                              {new Date(photo.captured_at).toLocaleDateString()}
                            </p>
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
                <span className="text-sm text-gray-600">Failed</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
