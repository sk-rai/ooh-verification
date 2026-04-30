import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'

interface Location {
  id: string
  address: string
  latitude: string
  longitude: string
  radius_meters: string
}

export default function CreateCampaign() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    campaign_type: 'ooh',
    start_date: '',
    end_date: '',
    delivery_window_start: '',
    delivery_window_end: '',
  })

  const [locations, setLocations] = useState<Location[]>([
    { id: '1', address: '', latitude: '', longitude: '', radius_meters: '100' }
  ])

  const [geocoding, setGeocoding] = useState(false)
  const [geocodeMessage, setGeocodeMessage] = useState('')

  const geocodeAddress = async (locationId: string) => {
    const loc = locations.find(l => l.id === locationId)
    if (!loc || !loc.address.trim()) return
    setGeocoding(true)
    setGeocodeMessage('')
    try {
      const res = await api.post('/api/campaigns/geocode', { address: loc.address })
      if (res.data && res.data.latitude && res.data.longitude) {
        updateLocation(locationId, 'latitude', String(res.data.latitude))
        updateLocation(locationId, 'longitude', String(res.data.longitude))
        setGeocodeMessage(`Resolved: ${res.data.formatted_address} (${res.data.latitude}, ${res.data.longitude})`)
      }
    } catch (err) {
      setGeocodeMessage('Could not resolve address. Please enter coordinates manually.')
    } finally {
      setGeocoding(false)
    }
  }

  const reverseGeocodeCoords = async (locationId: string) => {
    const loc = locations.find(l => l.id === locationId)
    if (!loc || !loc.latitude || !loc.longitude) return
    setGeocoding(true)
    setGeocodeMessage('')
    try {
      const res = await api.post('/api/campaigns/reverse-geocode', {
        latitude: parseFloat(loc.latitude),
        longitude: parseFloat(loc.longitude),
      })
      if (res.data && res.data.formatted_address) {
        updateLocation(locationId, 'address', res.data.formatted_address)
        setGeocodeMessage(`Resolved: ${res.data.formatted_address}`)
      }
    } catch (err) {
      setGeocodeMessage('Could not resolve coordinates to address.')
    } finally {
      setGeocoding(false)
    }
  }

  const addLocation = () => {
    setLocations([
      ...locations,
      { id: Date.now().toString(), address: '', latitude: '', longitude: '', radius_meters: '100' }
    ])
  }

  const removeLocation = (id: string) => {
    if (locations.length > 1) {
      setLocations(locations.filter(loc => loc.id !== id))
    }
  }

  const updateLocation = (id: string, field: keyof Location, value: string) => {
    setLocations(prev => prev.map(loc => 
      loc.id === id ? { ...loc, [field]: value } : loc
    ))
  }

  const validateLocations = () => {
    for (let i = 0; i < locations.length; i++) {
      const loc = locations[i]
      const hasAddress = loc.address.trim() !== ''
      const hasCoordinates = loc.latitude !== '' && loc.longitude !== ''
      
      if (!hasAddress && !hasCoordinates) {
        return `Location ${i + 1}: Please provide either a street address OR coordinates`
      }
      
      // If coordinates are partially filled
      if ((loc.latitude !== '' && loc.longitude === '') || (loc.latitude === '' && loc.longitude !== '')) {
        return `Location ${i + 1}: Please provide both latitude and longitude`
      }
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    // Validate locations
    const validationError = validateLocations()
    if (validationError) {
      setError(validationError)
      setLoading(false)
      return
    }

    try {
      // For now, we'll create campaign with first location
      // TODO: Backend needs to support multiple locations
      const firstLocation = locations[0]
      
      // If only address is provided, we'd need geocoding service
      // For now, require coordinates for actual creation
      if (!firstLocation.latitude || !firstLocation.longitude) {
        setError('Please provide coordinates for at least the first location. Geocoding support coming soon!')
        setLoading(false)
        return
      }
      
      const locationProfile: any = {
          tolerance_meters: parseFloat(firstLocation.radius_meters),
        }
      // Send coordinates if available
      if (firstLocation.latitude && firstLocation.longitude) {
        locationProfile.expected_latitude = parseFloat(firstLocation.latitude)
        locationProfile.expected_longitude = parseFloat(firstLocation.longitude)
      }
      // Send address for server-side geocoding if coordinates missing
      if (firstLocation.address.trim()) {
        locationProfile.address = firstLocation.address.trim()
      }
      // Add delivery window if set
      if (formData.campaign_type === 'delivery') {
        if (formData.delivery_window_start) {
          locationProfile.delivery_window_start = new Date(formData.delivery_window_start).toISOString()
        }
        if (formData.delivery_window_end) {
          locationProfile.delivery_window_end = new Date(formData.delivery_window_end).toISOString()
        }
      }
      await api.post('/api/campaigns', {
        name: formData.name,
        campaign_type: formData.campaign_type,
        start_date: new Date(formData.start_date).toISOString(),
        end_date: new Date(formData.end_date).toISOString(),
        location_profile: locationProfile,
      })

      navigate('/campaigns')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Failed to create campaign')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    })
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Create Campaign</h2>
            <p className="text-gray-600 mt-1">Set up a new photo verification campaign</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Basic Information */}
            <div className="bg-white shadow rounded-lg p-6 space-y-6">
              <h3 className="text-lg font-medium text-gray-900">Basic Information</h3>
              
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                  Campaign Name *
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  required
                  value={formData.name}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  placeholder="e.g., Store Verification Q1 2026"
                />
              </div>

              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                  Description
                </label>
                <textarea
                  id="description"
                  name="description"
                  rows={3}
                  value={formData.description}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  placeholder="Describe the purpose of this campaign..."
                />
              </div>

              <div>
                <label htmlFor="campaign_type" className="block text-sm font-medium text-gray-700">
                  Campaign Type *
                </label>
                <select
                  id="campaign_type"
                  name="campaign_type"
                  value={formData.campaign_type}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="ooh">OOH Advertising</option>
                  <option value="delivery">Delivery Verification</option>
                  <option value="construction">Construction</option>
                  <option value="insurance">Insurance</option>
                  <option value="healthcare">Healthcare</option>
                  <option value="property_management">Property Management</option>
                </select>
                {formData.campaign_type === 'delivery' && (
                  <p className="mt-1 text-xs text-blue-600">
                    Delivery campaigns use a wider geofence (150m default) and support time-window enforcement.
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label htmlFor="start_date" className="block text-sm font-medium text-gray-700">
                    Start Date *
                  </label>
                  <input
                    type="date"
                    id="start_date"
                    name="start_date"
                    required
                    value={formData.start_date}
                    onChange={handleChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label htmlFor="end_date" className="block text-sm font-medium text-gray-700">
                    End Date *
                  </label>
                  <input
                    type="date"
                    id="end_date"
                    name="end_date"
                    required
                    value={formData.end_date}
                    onChange={handleChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Delivery Time Window (only for delivery campaigns) */}
              {formData.campaign_type === 'delivery' && (
                <div className="mt-6 border-t border-gray-200 pt-6">
                  <h4 className="text-sm font-medium text-gray-900 mb-1">Delivery Time Window</h4>
                  <p className="text-xs text-gray-500 mb-4">
                    Photos captured outside this window will be flagged. Leave empty to skip time validation.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label htmlFor="delivery_window_start" className="block text-sm font-medium text-gray-700">
                        Window Start
                      </label>
                      <input
                        type="datetime-local"
                        id="delivery_window_start"
                        name="delivery_window_start"
                        value={formData.delivery_window_start}
                        onChange={handleChange}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label htmlFor="delivery_window_end" className="block text-sm font-medium text-gray-700">
                        Window End
                      </label>
                      <input
                        type="datetime-local"
                        id="delivery_window_end"
                        name="delivery_window_end"
                        value={formData.delivery_window_end}
                        onChange={handleChange}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Target Locations */}
            <div className="bg-white shadow rounded-lg p-6 space-y-6">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Target Locations</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Add one or more locations where photos should be captured
                  </p>
                </div>
                <button
                  type="button"
                  onClick={addLocation}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                >
                  <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Location
                </button>
              </div>

              <div className="space-y-4">
                {locations.map((location, index) => (
                  <div key={location.id} className="border border-gray-200 rounded-lg p-4 space-y-4">
                    <div className="flex justify-between items-start">
                      <h4 className="text-sm font-medium text-gray-900">
                        Location {index + 1}
                      </h4>
                      {locations.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeLocation(location.id)}
                          className="text-red-600 hover:text-red-800 text-sm"
                        >
                          Remove
                        </button>
                      )}
                    </div>

                    {/* Street Address Section */}
                    <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <label className="block text-sm font-medium text-gray-700">
                          Street Address
                        </label>
                        <span className="text-xs text-gray-500 bg-white px-2 py-1 rounded">
                          Option 1
                        </span>
                      </div>
                      <input
                        type="text"
                        value={location.address}
                        onChange={(e) => updateLocation(location.id, 'address', e.target.value)}
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                        placeholder="e.g., 123 Main St, City, State, ZIP"
                      />
                      <div className="flex items-center gap-2 mt-2">
                        <button
                          type="button"
                          onClick={() => geocodeAddress(location.id)}
                          disabled={geocoding || !location.address.trim()}
                          className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
                        >
                          {geocoding ? 'Resolving...' : 'Resolve to Coordinates'}
                        </button>
                        <p className="text-xs text-gray-500">
                          Auto-fills lat/lng from address
                        </p>
                      </div>
                    </div>

                    {/* OR Divider */}
                    <div className="relative">
                      <div className="absolute inset-0 flex items-center">
                        <div className="w-full border-t border-gray-300"></div>
                      </div>
                      <div className="relative flex justify-center text-sm">
                        <span className="px-2 bg-white text-gray-500 font-medium">OR</span>
                      </div>
                    </div>

                    {/* Coordinates Section */}
                    <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <label className="block text-sm font-medium text-gray-700">
                          GPS Coordinates
                        </label>
                        <span className="text-xs text-gray-500 bg-white px-2 py-1 rounded">
                          Option 2
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Latitude
                          </label>
                          <input
                            type="number"
                            step="0.0000001"
                            value={location.latitude}
                            onChange={(e) => updateLocation(location.id, 'latitude', e.target.value)}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                            placeholder="12.9715987"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Longitude
                          </label>
                          <input
                            type="number"
                            step="0.0000001"
                            value={location.longitude}
                            onChange={(e) => updateLocation(location.id, 'longitude', e.target.value)}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                            placeholder="77.5945627"
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-2">
                        <button
                          type="button"
                          onClick={() => reverseGeocodeCoords(location.id)}
                          disabled={geocoding || !location.latitude || !location.longitude}
                          className="px-3 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50"
                        >
                          {geocoding ? 'Resolving...' : 'Resolve to Address'}
                        </button>
                        <p className="text-xs text-gray-500">
                          Auto-fills address from coordinates
                        </p>
                      </div>
                    </div>

                    {/* Radius */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Verification Radius (meters) *
                      </label>
                      <input
                        type="number"
                        required
                        min="10"
                        max="5000"
                        value={location.radius_meters}
                        onChange={(e) => updateLocation(location.id, 'radius_meters', e.target.value)}
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Photos must be taken within this radius of the target location
                      </p>
                    </div>

                    {/* Geocode result message */}
                    {geocodeMessage && (
                      <div className="bg-blue-50 border border-blue-200 rounded p-3">
                        <p className="text-xs text-blue-800">{geocodeMessage}</p>
                      </div>
                    )}

                    {/* Validation indicator */}
                    {location.address === '' && location.latitude === '' && location.longitude === '' && (
                      <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                        <p className="text-xs text-yellow-800">
                          ⚠️ Please provide either a street address OR coordinates for this location
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {locations.length > 1 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <p className="text-sm text-blue-800">
                    <strong>{locations.length} locations</strong> will be created for this campaign.
                    Free plan: up to 5 locations | Pro: up to 500 | Enterprise: unlimited
                  </p>
                </div>
              )}
            </div>

            {/* Campaign Scope Info */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-blue-900 mb-2">Campaign Scope Examples</h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• <strong>Local:</strong> Single location (e.g., one store or office)</li>
                <li>• <strong>Regional:</strong> Multiple locations in a city/region (e.g., 10 stores)</li>
                <li>• <strong>National:</strong> Locations across the country (e.g., 100+ stores)</li>
              </ul>
            </div>

            <div className="flex justify-end space-x-3 pt-6">
              <button
                type="button"
                onClick={() => navigate('/campaigns')}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create Campaign'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
