import { useState, useEffect, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { Country, State } from 'country-state-city'

export default function Register() {
  const [companyName, setCompanyName] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [title, setTitle] = useState('')
  const [contactPerson, setContactPerson] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [designation, setDesignation] = useState('')
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [countryCode, setCountryCode] = useState('')
  const [stateCode, setStateCode] = useState('')
  const [website, setWebsite] = useState('')
  const [industry, setIndustry] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register, isAuthenticated, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const countries = useMemo(() => Country.getAllCountries(), [])
  const states = useMemo(() => countryCode ? State.getStatesOfCountry(countryCode) : [], [countryCode])

  const selectedCountry = countries.find(c => c.isoCode === countryCode)
  const selectedState = states.find(s => s.isoCode === stateCode)

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, authLoading, navigate])

  // Reset state when country changes
  useEffect(() => { setStateCode('') }, [countryCode])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await register({
        email,
        password,
        company_name: companyName,
        phone_number: phoneNumber,
        title: title || undefined,
        contact_person: contactPerson || undefined,
        contact_phone: contactPhone || undefined,
        designation: designation || undefined,
        address: address || undefined,
        city: city || undefined,
        state: selectedState?.name || undefined,
        country: selectedCountry?.name || '',
        website: website || undefined,
        industry: industry || undefined,
      })
      navigate('/dashboard')
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail
      if (Array.isArray(errorDetail)) {
        setError(errorDetail.map((e: any) => e.msg).join(', '))
      } else if (typeof errorDetail === 'string') {
        setError(errorDetail)
      } else {
        setError('Registration failed. Please check your information and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const inputClass = "mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
  const labelClass = "block text-sm font-medium text-gray-700"
  const selectClass = "mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 text-gray-900 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-lg w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">TrustCapture</h2>
          <p className="mt-2 text-center text-sm text-gray-600">Create your account</p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="rounded-md bg-red-50 p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Account */}
          <div className="space-y-4">
            <p className="text-sm font-semibold text-gray-800">Account</p>
            <div>
              <label htmlFor="email" className={labelClass}>Email address *</label>
              <input id="email" type="email" required className={inputClass} placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label htmlFor="password" className={labelClass}>Password *</label>
              <input id="password" type="password" required minLength={8} className={inputClass} placeholder="Min 8 chars, 1 uppercase, 1 digit" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
          </div>

          {/* Contact Person */}
          <div className="space-y-4">
            <p className="text-sm font-semibold text-gray-800">Contact Person</p>
            <div className="grid grid-cols-4 gap-3">
              <div className="col-span-1">
                <label htmlFor="title" className={labelClass}>Title</label>
                <select id="title" className={selectClass} value={title} onChange={(e) => setTitle(e.target.value)}>
                  <option value="">--</option>
                  <option value="Mr">Mr</option>
                  <option value="Ms">Ms</option>
                  <option value="Mrs">Mrs</option>
                  <option value="Dr">Dr</option>
                  <option value="Prof">Prof</option>
                </select>
              </div>
              <div className="col-span-3">
                <label htmlFor="contactPerson" className={labelClass}>Full Name</label>
                <input id="contactPerson" type="text" className={inputClass} placeholder="Contact person name" value={contactPerson} onChange={(e) => setContactPerson(e.target.value)} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="contactPhone" className={labelClass}>Phone / Cell</label>
                <input id="contactPhone" type="tel" className={inputClass} placeholder="+1234567890" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
              </div>
              <div>
                <label htmlFor="designation" className={labelClass}>Designation</label>
                <input id="designation" type="text" className={inputClass} placeholder="e.g. CEO, Manager" value={designation} onChange={(e) => setDesignation(e.target.value)} />
              </div>
            </div>
          </div>

          {/* Company */}
          <div className="space-y-4">
            <p className="text-sm font-semibold text-gray-800">Company</p>
            <div>
              <label htmlFor="companyName" className={labelClass}>Company Name *</label>
              <input id="companyName" type="text" required minLength={2} className={inputClass} placeholder="Your Company" value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
            </div>
            <div>
              <label htmlFor="companyPhone" className={labelClass}>Company Phone *</label>
              <input id="companyPhone" type="tel" required className={inputClass} placeholder="+1234567890" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} />
              <p className="mt-1 text-xs text-gray-500">Include country code (e.g., +1 for US, +91 for India)</p>
            </div>
            <div>
              <label htmlFor="country" className={labelClass}>Country *</label>
              <select id="country" required className={selectClass} value={countryCode} onChange={(e) => setCountryCode(e.target.value)}>
                <option value="">Select Country</option>
                {countries.map(c => (
                  <option key={c.isoCode} value={c.isoCode}>{c.name}</option>
                ))}
              </select>
            </div>
            {states.length > 0 && (
              <div>
                <label htmlFor="state" className={labelClass}>State / Province</label>
                <select id="state" className={selectClass} value={stateCode} onChange={(e) => setStateCode(e.target.value)}>
                  <option value="">Select State</option>
                  {states.map(s => (
                    <option key={s.isoCode} value={s.isoCode}>{s.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label htmlFor="city" className={labelClass}>City</label>
              <input id="city" type="text" className={inputClass} placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
            </div>
            <div>
              <label htmlFor="address" className={labelClass}>Address</label>
              <input id="address" type="text" className={inputClass} placeholder="Street address" value={address} onChange={(e) => setAddress(e.target.value)} />
            </div>
            <div>
              <label htmlFor="website" className={labelClass}>Website (optional)</label>
              <input id="website" type="url" className={inputClass} placeholder="https://yourcompany.com" value={website} onChange={(e) => setWebsite(e.target.value)} />
            </div>
            <div>
              <label htmlFor="industry" className={labelClass}>Industry (optional)</label>
              <select id="industry" className={selectClass} value={industry} onChange={(e) => setIndustry(e.target.value)}>
                <option value="">Select Industry</option>
                <option value="OOH Advertising">OOH Advertising</option>
                <option value="Delivery & Logistics">Delivery & Logistics</option>
                <option value="Construction">Construction</option>
                <option value="Agriculture">Agriculture</option>
                <option value="Insurance">Insurance</option>
                <option value="Real Estate">Real Estate</option>
                <option value="Government">Government</option>
                <option value="Retail">Retail</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <div>
            <button type="submit" disabled={loading} className="group relative w-full flex justify-center py-2.5 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50">
              {loading ? 'Creating account...' : 'Create account'}
            </button>
            <p className="mt-2 text-center text-xs text-gray-400">No credit card required</p>
          </div>

          <div className="text-center">
            <Link to="/login" className="font-medium text-primary-600 hover:text-primary-500">
              Already have an account? Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
