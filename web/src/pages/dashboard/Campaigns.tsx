import { Link } from 'react-router-dom'
import Navigation from '../../components/Navigation'

export default function Campaigns() {
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

          <div className="bg-white shadow rounded-lg p-6">
            <p className="text-gray-500 text-center py-8">
              No campaigns yet. Create your first campaign to get started!
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
