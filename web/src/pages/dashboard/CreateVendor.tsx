import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navigation from '../../components/Navigation'
import api from '../../services/api'
import { Country, State } from 'country-state-city'

export default function CreateVendor() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [createdVendor, setCreatedVendor] = useState<any>(null)

  const [formData, setFormData] = useState({
    name: '',
    phone_number: '',
    email: '',
    city: '',
  })
  const [countryCode, setCountryCode] = useState('')
  const [stateCode, setStateCode] = useState('')

  const countries = useMemo(() => Country.getAllCountries(), [])
  const states = useMemo(() => countryCode ? State.getStatesOfCountry(countryCode) : [], [countryCode])
  const selectedCountry = countries.find(c => c.isoCode === countryCode)
  const selectedState = states.find(s => s.isoCode === stateCode)

  useEffect(() => { setStateCode('') }, [countryCode])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await api.post('/api/vendors', {
        name: formData.name,
        phone_number: formData.phone_number,
        email: formData.email || undefined,
        city: formData.city || undefined,
        state: selectedState?.name || undefined,
        country: selectedCountry?.name || undefined,
      })
      setCreatedVendor(response.data)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', '))
      } else if (typeof detail === 'object' && detail !== null) {
        setError(detail.msg || detail.message || JSON.stringify(detail))
      } else {
        setError(detail || 'Failed to create vendor')
      }
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const inputClass = "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
  const labelClass = "block text-sm font-medium text-gray-700"

  if (createdVendor) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Navigation />
        <main className="max-w-3xl mx-auto py-6 sm:px-6 lg:px-8">
          <div className="px-4 py-6 sm:px-0">
            <div className="bg-white shadow rounded-lg p-6">
              <div className="text-center">
                <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
                  <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="mt-4 text-lg font-medium text-gray-900">Vendor Created Successfully!</h3>
                <p className="mt-2 text-sm text-gray-500">Share these credentials with the vendor</p>
                <div className="mt-6 bg-gray-50 rounded-lg p-4 text-left">
                  <dl className="space-y-3">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Vendor ID</dt>
                      <dd className="mt-1 text-lg font-mono font-semibold text-gray-900">{createdVendor.vendor_id}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Name</dt>
                      <dd className="mt-1 text-sm text-gray-900">{createdVendor.name}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Phone Number</dt>
                      <dd className="mt-1 text-sm text-gray-900">{createdVendor.phone_number}</dd>
                    </div>
                    {createdVendor.email && (
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Email</dt>
                        <dd className="mt-1 text-sm text-gray-900">{createdVendor.email}</dd>
                      </div>
                    )}
                  </dl>
                </div>
                <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <p className="text-sm text-blue-800">
                    <strong>Important:</strong> The vendor will use their Vendor ID and phone number to log in to the mobile app. They will receive an OTP for authentication.
                  </p>
                </div>
                <div className="mt-6 flex justify-center space-x-3">
                  <button onClick={() => navigate('/vendors')} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                    View All Vendors
                  </button>
                  <button
                    onClick={() => {
                      setCreatedVendor(null)
                      setFormData({ name: '', phone_number: '', email: '', city: '' })
                      setCountryCode('')
                      setStateCode('')
                    }}
                    className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                  >
                    Add Another Vendor
                  </button>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />
      <main className="max-w-3xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Add Vendor</h2>
            <p className="text-gray-600 mt-1">Register a new field vendor</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 space-y-6">
            <div>
              <label htmlFor="name" className={labelClass}>Vendor Name *</label>
              <input type="text" id="name" name="name" required value={formData.name} onChange={handleChange} className={inputClass} placeholder="e.g., John Doe" />
            </div>

            <div>
              <label htmlFor="phone_number" className={labelClass}>Phone Number *</label>
              <input type="tel" id="phone_number" name="phone_number" required value={formData.phone_number} onChange={handleChange} className={inputClass} placeholder="+1234567890" />
              <p className="mt-1 text-sm text-gray-500">Include country code (e.g., +91 for India, +1 for US)</p>
            </div>

            <div>
              <label htmlFor="email" className={labelClass}>Email (Optional)</label>
              <input type="email" id="email" name="email" value={formData.email} onChange={handleChange} className={inputClass} placeholder="vendor@example.com" />
            </div>

            <div>
              <label htmlFor="country" className={labelClass}>Country</label>
              <select id="country" className={inputClass} value={countryCode} onChange={(e) => setCountryCode(e.target.value)}>
                <option value="">Select Country</option>
                {countries.map(c => (
                  <option key={c.isoCode} value={c.isoCode}>{c.name}</option>
                ))}
              </select>
            </div>

            {states.length > 0 && (
              <div>
                <label htmlFor="state" className={labelClass}>State / Province</label>
                <select id="state" className={inputClass} value={stateCode} onChange={(e) => setStateCode(e.target.value)}>
                  <option value="">Select State</option>
                  {states.map(s => (
                    <option key={s.isoCode} value={s.isoCode}>{s.name}</option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label htmlFor="city" className={labelClass}>City</label>
              <input type="text" id="city" name="city" value={formData.city} onChange={handleChange} className={inputClass} placeholder="City" />
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-sm text-yellow-800">
                <strong>Note:</strong> After creation, the vendor will receive a unique Vendor ID. They will use this ID along with their phone number to log in to the mobile app.
              </p>
            </div>

            <div className="flex justify-end space-x-3 pt-6 border-t">
              <button type="button" onClick={() => navigate('/vendors')} className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">
                Cancel
              </button>
              <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50">
                {loading ? 'Creating...' : 'Create Vendor'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
