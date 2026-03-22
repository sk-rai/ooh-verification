import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface Campaign {
  campaign_id: string
  name: string
  description: string
  campaign_code: string
  status: string
  start_date: string
  end_date: string
  target_location: {
    latitude: number
    longitude: number
  }
  radius_meters: number
  photos_count: number
  created_at: string
}

interface Vendor {
  vendor_id: string
  name: string
  phone_number: string
  status: string
}

interface Photo {
  photo_id: string
  vendor_id: string
  vendor_name: string
  captured_at: string
  verification_status: string
  confidence_score: number
  thumbnail_url?: string
}

export default function CampaignDetails() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [photos, setPhotos] = useState<Photo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'overview' | 'vendors' | 'photos'>('overview')

  useEffect(() => {
    fetchCampaignDetails()
  }, [id])

  const fetchCampaignDetails = async () => {
    try {
      const [campaignRes, vendorsRes, photosRes] = await Promise.all([
        api.get(`/api/campaigns/${id}`),
        api.get(`/api/campaigns/${id}/vendors`).catch(() => ({ data: [] })),
        api.get(`/api/campaigns/${id}/photos`).catch(() => ({ data: [] })),
      ])

      setCampaign(campaignRes.data)
      setVendors(vendorsRes.data)
      setPhotos(photosRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load campaign details')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800'
      case 'completed':
        return 'bg-gray-100 text-gray-800'
      case 'draft':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Navigation />
        <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <div className="px-4 py-6 sm:px-0">
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">Loading campaign details...</p>
            </div>
          </div>
        </main>
      </div>
    )
  }

  if (error || !campaign) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Navigation />
        <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <div className="px-4 py-6 sm:px-0">
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error || 'Campaign not found'}
            </div>
            <button
              onClick={() => navigate('/campaigns')}
              className="mt-4 text-blue-600 hover:text-blue-800"
            >
              ← Back to Campaigns
            </button>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Header */}
          <div className="mb-6">
            <button
              onClick={() => navigate('/campaigns')}
              className="text-gray-600 hover:text-gray-900 mb-2 flex items-center"
            >
              <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back to Campaigns
            </button>
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{campaign.name}</h2>
                <div className="mt-2 flex items-center space-x-4">
                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(campaign.status)}`}>
                    {campaign.status}
                  </span>
                  <span className="text-sm text-gray-500">Code: {campaign.campaign_code}</span>
                  <span className="text-sm text-gray-500">
                    {new Date(campaign.start_date).toLocaleDateString()} - {new Date(campaign.end_date).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <button
                onClick={() => navigate(`/campaigns/${id}/edit`)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Edit Campaign
              </button>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Photos Captured</dt>
                      <dd className="text-lg font-medium text-gray-900">{campaign.photos_count}</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Assigned Vendors</dt>
                      <dd className="text-lg font-medium text-gray-900">{vendors.length}</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Verification Radius</dt>
                      <dd className="text-lg font-medium text-gray-900">{campaign.radius_meters}m</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-white shadow rounded-lg">
            <div className="border-b border-gray-200">
              <nav className="flex -mb-px">
                <button
                  onClick={() => setActiveTab('overview')}
                  className={`py-4 px-6 text-sm font-medium ${
                    activeTab === 'overview'
                      ? 'border-b-2 border-blue-500 text-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setActiveTab('vendors')}
                  className={`py-4 px-6 text-sm font-medium ${
                    activeTab === 'vendors'
                      ? 'border-b-2 border-blue-500 text-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Vendors ({vendors.length})
                </button>
                <button
                  onClick={() => setActiveTab('photos')}
                  className={`py-4 px-6 text-sm font-medium ${
                    activeTab === 'photos'
                      ? 'border-b-2 border-blue-500 text-blue-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Photos ({photos.length})
                </button>
              </nav>
            </div>

            <div className="p-6">
              {/* Overview Tab */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {campaign.description && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-2">Description</h3>
                      <p className="text-sm text-gray-600">{campaign.description}</p>
                    </div>
                  )}

                  <div>
                    <h3 className="text-sm font-medium text-gray-900 mb-2">Target Location</h3>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <dl className="grid grid-cols-2 gap-4">
                        <div>
                          <dt className="text-xs font-medium text-gray-500">Latitude</dt>
                          <dd className="text-sm text-gray-900">{campaign.target_location.latitude}</dd>
                        </div>
                        <div>
                          <dt className="text-xs font-medium text-gray-500">Longitude</dt>
                          <dd className="text-sm text-gray-900">{campaign.target_location.longitude}</dd>
                        </div>
                      </dl>
                      <a
                        href={`https://www.google.com/maps?q=${campaign.target_location.latitude},${campaign.target_location.longitude}`}
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

                  <div>
                    <h3 className="text-sm font-medium text-gray-900 mb-2">Campaign Details</h3>
                    <dl className="grid grid-cols-2 gap-4">
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Created</dt>
                        <dd className="text-sm text-gray-900">{new Date(campaign.created_at).toLocaleString()}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Status</dt>
                        <dd className="text-sm text-gray-900 capitalize">{campaign.status}</dd>
                      </div>
                    </dl>
                  </div>
                </div>
              )}

              {/* Vendors Tab */}
              {activeTab === 'vendors' && (
                <div>
                  {vendors.length === 0 ? (
                    <p className="text-gray-500 text-center py-8">No vendors assigned to this campaign yet.</p>
                  ) : (
                    <div className="space-y-3">
                      {vendors.map((vendor) => (
                        <div key={vendor.vendor_id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
                          <div>
                            <p className="font-medium text-gray-900">{vendor.name}</p>
                            <p className="text-sm text-gray-500">{vendor.phone_number}</p>
                          </div>
                          <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(vendor.status)}`}>
                            {vendor.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Photos Tab */}
              {activeTab === 'photos' && (
                <div>
                  {photos.length === 0 ? (
                    <p className="text-gray-500 text-center py-8">No photos captured for this campaign yet.</p>
                  ) : (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      {photos.map((photo) => (
                        <Link
                          key={photo.photo_id}
                          to={`/photos/${photo.photo_id}`}
                          className="group relative aspect-square bg-gray-200 rounded-lg overflow-hidden hover:opacity-75"
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
                          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                            <span className={`text-xs px-2 py-1 rounded-full ${getVerificationColor(photo.verification_status)}`}>
                              {photo.verification_status}
                            </span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
