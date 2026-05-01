import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import BulkUploadTab from '../../components/BulkUploadTab'
import UpgradePrompt from '../../components/UpgradePrompt'
import { useAuth } from '../../contexts/AuthContext'
import api, { bulkOperations } from '../../services/api'
import { BulkOperationResponse } from '../../types'

interface LocationProfile {
  profile_id: string
  expected_latitude: number
  expected_longitude: number
  tolerance_meters: number
}

interface Campaign {
  campaign_id: string
  name: string
  description?: string
  campaign_code: string
  campaign_type: string
  status: string
  start_date: string
  end_date: string
  location_profile?: LocationProfile
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
  const { user } = useAuth()
  const { id } = useParams()
  const navigate = useNavigate()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [photos, setPhotos] = useState<Photo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'overview' | 'vendors' | 'photos'>('overview')
  const [vendorSubTab, setVendorSubTab] = useState<'list' | 'bulk'>('list')
  const [allVendors, setAllVendors] = useState<Vendor[]>([])
  const [selectedVendorIds, setSelectedVendorIds] = useState<string[]>([])
  const [assigning, setAssigning] = useState(false)
  const [assignError, setAssignError] = useState('')
  const [assignSuccess, setAssignSuccess] = useState('')

  const isPaidTier = user?.subscription_tier === 'pro' || user?.subscription_tier === 'enterprise'

  useEffect(() => {
    if (id) {
      fetchCampaignDetails()
      fetchVendors()
      fetchPhotos()
      fetchAllVendors()
    }
  }, [id])

  const fetchCampaignDetails = async () => {
    try {
      const response = await api.get(`/api/campaigns/${id}`)
      setCampaign(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load campaign')
      console.error('Error fetching campaign:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchVendors = async () => {
    try {
      const response = await api.get(`/api/campaigns/${id}/vendors`)
      setVendors(response.data.vendors || [])
    } catch (err: any) {
      console.error('Error fetching vendors:', err)
    }
  }

  const fetchPhotos = async () => {
    try {
      const response = await api.get(`/api/campaigns/${id}/photos`)
      setPhotos(response.data.photos || [])
    } catch (err: any) {
      // Photos endpoint may not exist yet - silently handle 404
      if (err.response?.status !== 404) {
        console.error('Error fetching photos:', err)
      }
    }
  }

  const fetchAllVendors = async () => {
    try {
      const response = await api.get('/api/vendors')
      setAllVendors(response.data.vendors || [])
    } catch (err: any) {
      console.error('Error fetching all vendors:', err)
    }
  }

  const handleToggleVendor = (vendorId: string) => {
    setSelectedVendorIds(prev =>
      prev.includes(vendorId)
        ? prev.filter(id => id !== vendorId)
        : [...prev, vendorId]
    )
  }

  const handleAssignVendors = async () => {
    if (selectedVendorIds.length === 0) {
      setAssignError('Please select at least one vendor')
      return
    }
    setAssigning(true)
    setAssignError('')
    setAssignSuccess('')
    try {
      await api.post(`/api/campaigns/${id}/vendors`, {
        vendor_ids: selectedVendorIds,
      })
      setAssignSuccess(`Successfully assigned ${selectedVendorIds.length} vendor(s)`)
      setSelectedVendorIds([])
      fetchVendors()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setAssignError(detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof detail === 'string') {
        setAssignError(detail)
      } else {
        setAssignError('Failed to assign vendors')
      }
    } finally {
      setAssigning(false)
    }
  }

  const handleUnassignVendor = async (vendorId: string) => {
    if (!confirm('Are you sure you want to unassign this vendor?')) return
    try {
      await api.delete(`/api/campaigns/${id}/vendors/${vendorId}`)
      fetchVendors()
    } catch (err: any) {
      console.error('Error unassigning vendor:', err)
    }
  }

  const handleBulkAssignment = async (file: File): Promise<BulkOperationResponse> => {
    const response = await bulkOperations.uploadAssignments(file)
    if (response.data.created.length > 0) {
      fetchVendors()
    }
    return response.data
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800'
      case 'completed':
        return 'bg-gray-100 text-gray-800'
      case 'draft':
        return 'bg-yellow-100 text-yellow-800'
      case 'inactive':
        return 'bg-gray-100 text-gray-800'
      case 'suspended':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getVerificationColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-100 text-green-800'
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
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
                      <dd className="text-lg font-medium text-gray-900">{photos.length}</dd>
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
                      <dt className="text-sm font-medium text-gray-500 truncate">Tolerance</dt>
                      <dd className="text-lg font-medium text-gray-900">{(Array.isArray(campaign.location_profile) ? campaign.location_profile[0]?.tolerance_meters : campaign.location_profile?.tolerance_meters) || 0}m</dd>
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
                    <h3 className="text-sm font-medium text-gray-900 mb-2">Target Locations</h3>
              {Array.isArray(campaign.location_profile) && campaign.location_profile.length > 0 ? (
                campaign.location_profile.map((loc: any, idx: number) => (
                  <div key={idx} className="mb-3 p-3 bg-gray-50 rounded-lg">
                    <p className="text-sm font-medium text-gray-700">Location {idx + 1}</p>
                    <p className="text-sm text-gray-600">
                      Latitude: {loc.expected_latitude?.toFixed(6)}, Longitude: {loc.expected_longitude?.toFixed(6)}
                    </p>
                    <p className="text-sm text-gray-600">Tolerance: {loc.tolerance_meters} meters</p>
                    {loc.resolved_address && (
                      <p className="text-sm text-gray-500">{loc.resolved_address}</p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500">No locations configured</p>
              )}

              <h4 className="text-md font-semibold text-gray-800 mt-4">Campaign Period</h4>
                    <p className="text-sm text-gray-600">
                      {new Date(campaign.start_date).toLocaleDateString()} - {new Date(campaign.end_date).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              )}

              {/* Vendors Tab */}
              {activeTab === 'vendors' && (
                <div>
                  {/* Vendor Sub-tabs */}
                  <div className="border-b border-gray-200 mb-6">
                    <nav className="flex -mb-px space-x-8">
                      <button
                        onClick={() => setVendorSubTab('list')}
                        className={`py-2 px-1 text-sm font-medium border-b-2 ${
                          vendorSubTab === 'list'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        }`}
                      >
                        Assigned Vendors ({vendors.length})
                      </button>
                      <button
                        onClick={() => setVendorSubTab('bulk')}
                        className={`py-2 px-1 text-sm font-medium border-b-2 flex items-center ${
                          vendorSubTab === 'bulk'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        } ${!isPaidTier ? 'opacity-50' : ''}`}
                        disabled={!isPaidTier}
                      >
                        Bulk Assign
                        {!isPaidTier && (
                          <svg className="ml-1 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                          </svg>
                        )}
                      </button>
                    </nav>
                  </div>

                  {/* Vendor List Sub-tab */}
                  {vendorSubTab === 'list' && (
                    <div>
                      {/* Assign Vendors Section */}
                      <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-gray-900 mb-3">Assign Vendors</h4>

                        {assignError && (
                          <div className="mb-3 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                            {assignError}
                          </div>
                        )}
                        {assignSuccess && (
                          <div className="mb-3 bg-green-50 border border-green-200 text-green-700 px-3 py-2 rounded text-sm">
                            {assignSuccess}
                          </div>
                        )}

                        {(() => {
                          const assignedIds = vendors.map(v => v.vendor_id)
                          const unassigned = allVendors.filter(v => !assignedIds.includes(v.vendor_id))

                          if (unassigned.length === 0) {
                            return (
                              <p className="text-sm text-gray-500">
                                {allVendors.length === 0
                                  ? 'No vendors created yet. Create vendors first.'
                                  : 'All vendors are already assigned to this campaign.'}
                              </p>
                            )
                          }

                          return (
                            <>
                              <div className="max-h-48 overflow-y-auto space-y-2 mb-3">
                                {unassigned.map((vendor) => (
                                  <label
                                    key={vendor.vendor_id}
                                    className="flex items-center p-2 rounded hover:bg-white cursor-pointer"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selectedVendorIds.includes(vendor.vendor_id)}
                                      onChange={() => handleToggleVendor(vendor.vendor_id)}
                                      className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                    />
                                    <div className="ml-3">
                                      <span className="text-sm font-medium text-gray-900">{vendor.name}</span>
                                      <span className="text-sm text-gray-500 ml-2">{vendor.phone_number}</span>
                                      <span className="text-xs text-gray-400 ml-2">ID: {vendor.vendor_id}</span>
                                    </div>
                                  </label>
                                ))}
                              </div>
                              <button
                                onClick={handleAssignVendors}
                                disabled={assigning || selectedVendorIds.length === 0}
                                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {assigning
                                  ? 'Assigning...'
                                  : `Assign ${selectedVendorIds.length} Vendor${selectedVendorIds.length !== 1 ? 's' : ''}`}
                              </button>
                            </>
                          )
                        })()}
                      </div>

                      {/* Assigned Vendors List */}
                      <h4 className="text-sm font-medium text-gray-900 mb-3">Currently Assigned</h4>
                      {vendors.length === 0 ? (
                        <p className="text-gray-500 text-center py-4 text-sm">No vendors assigned to this campaign yet.</p>
                      ) : (
                        <div className="space-y-3">
                          {vendors.map((vendor) => (
                            <div
                              key={vendor.vendor_id}
                              className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50"
                            >
                              <div>
                                <p className="font-medium text-gray-900">{vendor.name}</p>
                                <p className="text-sm text-gray-500">{vendor.phone_number}</p>
                                <p className="text-xs text-gray-400">ID: {vendor.vendor_id}</p>
                              </div>
                              <div className="flex items-center space-x-3">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(vendor.status)}`}>
                                  {vendor.status}
                                </span>
                                <button
                                  onClick={() => handleUnassignVendor(vendor.vendor_id)}
                                  className="text-red-500 hover:text-red-700 text-sm"
                                  title="Unassign vendor"
                                >
                                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                  </svg>
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Bulk Assign Sub-tab */}
                  {vendorSubTab === 'bulk' && (
                    <div>
                      {isPaidTier ? (
                        <BulkUploadTab
                          templateType="assignments"
                          onUpload={handleBulkAssignment}
                          title="Bulk Vendor Assignment"
                          description={`Assign multiple vendors to ${campaign.name} at once`}
                          instructions={[
                            'Download the CSV template below',
                            `Fill in vendor assignments for campaign code: ${campaign.campaign_code}`,
                            'Optionally include location data for each assignment',
                            'Upload the completed CSV file',
                          ]}
                        />
                      ) : (
                        <UpgradePrompt feature="Bulk Vendor Assignment" />
                      )}
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
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                                />
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
