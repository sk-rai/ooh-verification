import { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { Link } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface Stats {
  campaigns: number
  vendors: number
  photos: number
}

interface RecentPhoto {
  photo_id: string
  campaign_name: string
  vendor_name: string
  captured_at: string
  verification_status: string
  thumbnail_url?: string
}

export default function Dashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState<Stats>({ campaigns: 0, vendors: 0, photos: 0 })
  const [recentPhotos, setRecentPhotos] = useState<RecentPhoto[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      const [campaignsRes, vendorsRes, photosRes] = await Promise.all([
        api.get('/api/campaigns').catch(() => ({ data: [] })),
        api.get('/api/vendors').catch(() => ({ data: [] })),
        api.get('/api/photos?limit=6').catch(() => ({ data: [] })),
      ])

      setStats({
        campaigns: campaignsRes.data.length,
        vendors: vendorsRes.data.length,
        photos: (Array.isArray(photosRes.data) ? photosRes.data : (photosRes.data?.photos || [])).length,
      })

      const photosArr = Array.isArray(photosRes.data) ? photosRes.data : (photosRes.data?.photos || [])
      setRecentPhotos(photosArr.slice(0, 6))
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
    } finally {
      setLoading(false)
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

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Welcome back, {user?.company_name}!
          </h2>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Link to="/campaigns" className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Active Campaigns
                      </dt>
                      <dd className="text-lg font-medium text-gray-900">
                        {loading ? '...' : stats.campaigns}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </Link>

            <Link to="/vendors" className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Total Vendors
                      </dt>
                      <dd className="text-lg font-medium text-gray-900">
                        {loading ? '...' : stats.vendors}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </Link>

            <Link to="/photos" className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition">
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
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Photos Captured
                      </dt>
                      <dd className="text-lg font-medium text-gray-900">
                        {loading ? '...' : stats.photos}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </Link>
          </div>

          {/* Recent Photos */}
          {recentPhotos.length > 0 && (
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">Recent Photos</h3>
                <Link to="/photos" className="text-sm text-blue-600 hover:text-blue-800">
                  View All →
                </Link>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                {recentPhotos.map((photo) => (
                  <Link
                    key={photo.photo_id}
                    to="/photos"
                    className="group relative aspect-square bg-gray-200 rounded-lg overflow-hidden hover:opacity-75 transition"
                  >
                    {photo.thumbnail_url ? (
                      <img src={photo.thumbnail_url} alt="Photo" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <svg className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
            </div>
          )}

          {/* Empty State - Only show if no data */}
          {!loading && stats.campaigns === 0 && stats.vendors === 0 && stats.photos === 0 && (
            <div className="bg-white shadow rounded-lg p-6">
              <div className="text-center py-8">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">Get Started</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Start by creating a campaign and adding vendors to begin capturing photos.
                </p>
                <div className="mt-6 flex justify-center space-x-3">
                  <Link
                    to="/campaigns/new"
                    className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                  >
                    Create Campaign
                  </Link>
                  <Link
                    to="/vendors/new"
                    className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Add Vendor
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
