import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface Photo {
  photo_id: string
  campaign_id: string
  campaign_name: string
  vendor_id: string
  vendor_name: string
  captured_at: string
  verification_status: string
  confidence_score: number
  gps_latitude: number
  gps_longitude: number
  gps_accuracy: number
  thumbnail_url?: string
  photo_url?: string
}

interface PhotoDetailModalProps {
  photo: Photo | null
  onClose: () => void
}

function PhotoDetailModal({ photo, onClose }: PhotoDetailModalProps) {
  if (!photo) return null

  const getVerificationColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="p-6">
          {/* Header */}
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Photo Details</h3>
              <p className="text-sm text-gray-500">ID: {photo.photo_id}</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Photo */}
          <div className="mb-6">
            {photo.photo_url ? (
              <img src={photo.photo_url} alt="Photo" className="w-full rounded-lg" />
            ) : (
              <div className="w-full aspect-video bg-gray-200 rounded-lg flex items-center justify-center">
                <svg className="h-24 w-24 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            )}
          </div>

          {/* Verification Status */}
          <div className="mb-6">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Verification Status</h4>
            <div className="flex items-center space-x-4">
              <span className={`px-3 py-1 text-sm font-semibold rounded-full ${getVerificationColor(photo.verification_status)}`}>
                {photo.verification_status}
              </span>
              <div className="flex items-center">
                <span className="text-sm text-gray-500 mr-2">Confidence:</span>
                <div className="flex-1 bg-gray-200 rounded-full h-2 w-32">
                  <div
                    className={`h-2 rounded-full ${
                      photo.confidence_score >= 0.8 ? 'bg-green-500' :
                      photo.confidence_score >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${photo.confidence_score * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-gray-900 ml-2">
                  {(photo.confidence_score * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-6">
            {/* Campaign & Vendor */}
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3">Campaign & Vendor</h4>
              <dl className="space-y-2">
                <div>
                  <dt className="text-xs text-gray-500">Campaign</dt>
                  <dd className="text-sm text-gray-900">
                    <Link to={`/campaigns/${photo.campaign_id}`} className="text-blue-600 hover:text-blue-800">
                      {photo.campaign_name}
                    </Link>
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Vendor</dt>
                  <dd className="text-sm text-gray-900">{photo.vendor_name}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Captured At</dt>
                  <dd className="text-sm text-gray-900">{new Date(photo.captured_at).toLocaleString()}</dd>
                </div>
              </dl>
            </div>

            {/* GPS Data */}
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3">GPS Data</h4>
              <dl className="space-y-2">
                <div>
                  <dt className="text-xs text-gray-500">Latitude</dt>
                  <dd className="text-sm text-gray-900 font-mono">{photo.gps_latitude.toFixed(7)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Longitude</dt>
                  <dd className="text-sm text-gray-900 font-mono">{photo.gps_longitude.toFixed(7)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Accuracy</dt>
                  <dd className="text-sm text-gray-900">{photo.gps_accuracy.toFixed(1)}m</dd>
                </div>
              </dl>
              <a
                href={`https://www.google.com/maps?q=${photo.gps_latitude},${photo.gps_longitude}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
              >
                View on Google Maps
                <svg className="ml-1 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function PhotoGallery() {
  const [photos, setPhotos] = useState<Photo[]>([])
  const [filteredPhotos, setFilteredPhotos] = useState<Photo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null)
  
  const [filters, setFilters] = useState({
    campaign: '',
    vendor: '',
    status: '',
    dateFrom: '',
    dateTo: '',
  })

  const [campaigns, setCampaigns] = useState<Array<{ campaign_id: string; name: string }>>([])
  const [vendors, setVendors] = useState<Array<{ vendor_id: string; name: string }>>([])

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    applyFilters()
  }, [photos, filters])

  const fetchData = async () => {
    try {
      const [photosRes, campaignsRes, vendorsRes] = await Promise.all([
        api.get('/api/photos'),
        api.get('/api/campaigns'),
        api.get('/api/vendors'),
      ])

      setPhotos(photosRes.data)
      setCampaigns(campaignsRes.data)
      setVendors(vendorsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load photos')
    } finally {
      setLoading(false)
    }
  }

  const applyFilters = () => {
    let filtered = [...photos]

    if (filters.campaign) {
      filtered = filtered.filter(p => p.campaign_id === filters.campaign)
    }

    if (filters.vendor) {
      filtered = filtered.filter(p => p.vendor_id === filters.vendor)
    }

    if (filters.status) {
      filtered = filtered.filter(p => p.verification_status === filters.status)
    }

    if (filters.dateFrom) {
      filtered = filtered.filter(p => new Date(p.captured_at) >= new Date(filters.dateFrom))
    }

    if (filters.dateTo) {
      filtered = filtered.filter(p => new Date(p.captured_at) <= new Date(filters.dateTo))
    }

    setFilteredPhotos(filtered)
  }

  const resetFilters = () => {
    setFilters({
      campaign: '',
      vendor: '',
      status: '',
      dateFrom: '',
      dateTo: '',
    })
  }

  const getVerificationColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Photo Gallery</h2>
            <p className="text-gray-600 mt-1">Browse and filter captured photos</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Filters */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">Filters</h3>
              <button
                onClick={resetFilters}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Reset Filters
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Campaign</label>
                <select
                  value={filters.campaign}
                  onChange={(e) => setFilters({ ...filters, campaign: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">All Campaigns</option>
                  {campaigns.map((c) => (
                    <option key={c.campaign_id} value={c.campaign_id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
                <select
                  value={filters.vendor}
                  onChange={(e) => setFilters({ ...filters, vendor: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">All Vendors</option>
                  {vendors.map((v) => (
                    <option key={v.vendor_id} value={v.vendor_id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
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

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">From Date</label>
                <input
                  type="date"
                  value={filters.dateFrom}
                  onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">To Date</label>
                <input
                  type="date"
                  value={filters.dateTo}
                  onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="mt-4 text-sm text-gray-600">
              Showing {filteredPhotos.length} of {photos.length} photos
            </div>
          </div>

          {/* Photo Grid */}
          {loading ? (
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">Loading photos...</p>
            </div>
          ) : filteredPhotos.length === 0 ? (
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">
                {photos.length === 0 ? 'No photos captured yet.' : 'No photos match the selected filters.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {filteredPhotos.map((photo) => (
                <button
                  key={photo.photo_id}
                  onClick={() => setSelectedPhoto(photo)}
                  className="group relative aspect-square bg-gray-200 rounded-lg overflow-hidden hover:opacity-75 transition"
                >
                  {photo.thumbnail_url ? (
                    <img src={photo.thumbnail_url} alt="Photo" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <svg className="h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition" />
                  <div className="absolute bottom-0 left-0 right-0 p-2">
                    <span className={`text-xs px-2 py-1 rounded-full ${getVerificationColor(photo.verification_status)}`}>
                      {photo.verification_status}
                    </span>
                    <p className="text-xs text-white mt-1 truncate">{photo.campaign_name}</p>
                  </div>
                  <div className="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                    {(photo.confidence_score * 100).toFixed(0)}%
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Photo Detail Modal */}
      <PhotoDetailModal photo={selectedPhoto} onClose={() => setSelectedPhoto(null)} />
    </div>
  )
}
