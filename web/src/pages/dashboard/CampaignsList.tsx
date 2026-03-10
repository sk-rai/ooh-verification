import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
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
  photos_count: number
  created_at: string
}

export default function CampaignsList() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchCampaigns()
  }, [])

  const fetchCampaigns = async () => {
    try {
      const response = await api.get('/api/campaigns')
      setCampaigns(response.data.campaigns || [])
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load campaigns')
      console.error('Error fetching campaigns:', err)
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

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Campaigns</h2>
            <Link
              to="/campaigns/new"
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            >
              Create Campaign
            </Link>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {loading ? (
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">Loading campaigns...</p>
            </div>
          ) : campaigns.length === 0 ? (
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
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">No campaigns</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Get started by creating a new campaign.
                </p>
                <div className="mt-6">
                  <Link
                    to="/campaigns/new"
                    className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                  >
                    Create Campaign
                  </Link>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
              <ul className="divide-y divide-gray-200">
                {campaigns.map((campaign) => (
                  <li key={campaign.campaign_id}>
                    <Link
                      to={`/campaigns/${campaign.campaign_id}`}
                      className="block hover:bg-gray-50 transition"
                    >
                      <div className="px-4 py-4 sm:px-6">
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-3">
                              <p className="text-lg font-medium text-blue-600 truncate">
                                {campaign.name}
                              </p>
                              <span
                                className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(
                                  campaign.status
                                )}`}
                              >
                                {campaign.status}
                              </span>
                            </div>
                            {campaign.description && (
                              <p className="mt-1 text-sm text-gray-500 line-clamp-1">
                                {campaign.description}
                              </p>
                            )}
                            <div className="mt-2 flex items-center text-sm text-gray-500 space-x-4">
                              <span className="flex items-center">
                                <svg
                                  className="flex-shrink-0 mr-1.5 h-4 w-4 text-gray-400"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                                  />
                                </svg>
                                Code: {campaign.campaign_code}
                              </span>
                              <span className="flex items-center">
                                <svg
                                  className="flex-shrink-0 mr-1.5 h-4 w-4 text-gray-400"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                                  />
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                                  />
                                </svg>
                                {campaign.photos_count || 0} photos
                              </span>
                              <span>
                                {new Date(campaign.start_date).toLocaleDateString()} -{' '}
                                {new Date(campaign.end_date).toLocaleDateString()}
                              </span>
                            </div>
                          </div>
                          <div className="ml-5 flex-shrink-0">
                            <svg
                              className="h-5 w-5 text-gray-400"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 5l7 7-7 7"
                              />
                            </svg>
                          </div>
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
