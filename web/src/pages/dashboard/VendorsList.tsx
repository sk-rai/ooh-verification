import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import TabNavigation from '../../components/TabNavigation'
import BulkUploadTab from '../../components/BulkUploadTab'
import UpgradePrompt from '../../components/UpgradePrompt'
import { useAuth } from '../../contexts/AuthContext'
import api, { bulkOperations } from '../../services/api'
import { BulkOperationResponse } from '../../types'

interface Vendor {
  vendor_id: string
  name: string
  phone_number: string
  email?: string
  status: string
  created_at: string
  last_login_at?: string
}

export default function VendorsList() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('list')
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const isPaidTier = user?.subscription_tier === 'pro' || user?.subscription_tier === 'enterprise'

  const tabs = [
    {
      id: 'list',
      label: 'Vendor List',
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
      ),
    },
    {
      id: 'bulk',
      label: 'Bulk Upload',
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      ),
      locked: !isPaidTier,
      lockedMessage: 'Upgrade to PRO or ENTERPRISE to access bulk uploads',
    },
  ]

  useEffect(() => {
    if (activeTab === 'list') {
      fetchVendors()
    }
  }, [activeTab])

  const fetchVendors = async () => {
    try {
      const response = await api.get('/api/vendors')
      setVendors(response.data.vendors || [])
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load vendors')
      console.error('Error fetching vendors:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleBulkUpload = async (file: File): Promise<BulkOperationResponse> => {
    const response = await bulkOperations.uploadVendors(file)
    if (response.data.created.length > 0) {
      fetchVendors()
    }
    return response.data
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800'
      case 'inactive':
        return 'bg-gray-100 text-gray-800'
      case 'suspended':
        return 'bg-red-100 text-red-800'
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
            <h2 className="text-2xl font-bold text-gray-900">Vendors</h2>
            {activeTab === 'list' && (
              <Link
                to="/vendors/new"
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >
                Add Vendor
              </Link>
            )}
          </div>

          <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} className="mb-6" />

          {activeTab === 'list' && (
            <>
              {error && (
                <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                  {error}
                </div>
              )}

              {loading ? (
                <div className="bg-white shadow rounded-lg p-6">
                  <p className="text-gray-500 text-center py-8">Loading vendors...</p>
                </div>
              ) : vendors.length === 0 ? (
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
                        d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                      />
                    </svg>
                    <h3 className="mt-2 text-sm font-medium text-gray-900">No vendors</h3>
                    <p className="mt-1 text-sm text-gray-500">
                      Get started by adding a new vendor.
                    </p>
                    <div className="mt-6">
                      <Link
                        to="/vendors/new"
                        className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                      >
                        Add Vendor
                      </Link>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white shadow overflow-hidden sm:rounded-lg">
                  <ul className="divide-y divide-gray-200">
                    {vendors.map((vendor) => (
                      <li key={vendor.vendor_id} className="px-4 py-4 sm:px-6 hover:bg-gray-50">
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-3">
                              <p className="text-lg font-medium text-gray-900 truncate">
                                {vendor.name}
                              </p>
                              <span
                                className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(
                                  vendor.status
                                )}`}
                              >
                                {vendor.status}
                              </span>
                            </div>
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
                                ID: {vendor.vendor_id}
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
                                    d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                                  />
                                </svg>
                                {vendor.phone_number}
                              </span>
                              {vendor.email && (
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
                                      d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                                    />
                                  </svg>
                                  {vendor.email}
                                </span>
                              )}
                            </div>
                            <div className="mt-1 text-xs text-gray-400">
                              {vendor.last_login_at
                                ? `Last login: ${new Date(vendor.last_login_at).toLocaleString()}`
                                : 'Never logged in'}
                            </div>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {activeTab === 'bulk' && (
            <div className="bg-white shadow rounded-lg p-6">
              {isPaidTier ? (
                <BulkUploadTab
                  templateType="vendors"
                  onUpload={handleBulkUpload}
                  title="Bulk Vendor Upload"
                  description="Upload multiple vendors at once using a CSV file"
                  instructions={[
                    'Download the CSV template below',
                    'Fill in your vendor data (phone numbers must be in E.164 format: +1234567890)',
                    'Upload the completed CSV file',
                    'Review the results and fix any errors if needed',
                  ]}
                />
              ) : (
                <UpgradePrompt feature="Bulk Vendor Upload" />
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
