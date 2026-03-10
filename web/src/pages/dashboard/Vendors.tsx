import { Link } from 'react-router-dom'
import Navigation from '../../components/Navigation'

export default function Vendors() {
  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Vendors</h2>
            <Link
              to="/vendors/new"
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            >
              Add Vendor
            </Link>
          </div>

          <div className="bg-white shadow rounded-lg p-6">
            <p className="text-gray-500 text-center py-8">
              No vendors yet. Add your first vendor to start collecting photos!
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
