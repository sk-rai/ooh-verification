import { useState } from 'react'
import { Link } from 'react-router-dom'

const tiers = [
  {
    name: 'Free',
    priceINR: '₹0',
    priceUSD: '$0',
    period: '/month',
    desc: 'Get started and explore',
    features: ['50 photos/month', '5 vendors', '10 campaigns', '5 locations/campaign', '100 MB storage', 'Email notifications'],
    cta: 'Start Free Trial',
    ctaLink: '/register',
    badge: null,
    highlight: false,
    micro: 'No credit card required',
  },
  {
    name: 'Pro',
    priceINR: '₹999',
    priceUSD: '$15',
    period: '/month',
    yearlyINR: '₹9,990/year + GST — save 17%',
    yearlyUSD: '$150/year — save 17%',
    desc: 'For growing teams',
    features: ['1,000 photos/month', '10 vendors', '50 campaigns', '500 locations/campaign', '10 GB storage', 'Priority support', 'PDF, CSV, GeoJSON exports', 'Bulk CSV operations'],
    cta: 'Start Free Trial',
    ctaLink: '/register',
    badge: 'Most Popular',
    highlight: true,
    micro: 'Cancel anytime',
  },
  {
    name: 'Enterprise',
    priceINR: '₹4,999',
    priceUSD: '$75',
    period: '/month',
    yearlyINR: '₹49,990/year + GST — save 17%',
    yearlyUSD: '$750/year — save 17%',
    desc: 'For large organizations',
    features: ['Unlimited photos', 'Unlimited vendors', 'Unlimited campaigns', 'Unlimited locations/campaign', '100 GB storage', 'Dedicated support', 'Custom branding & domain', 'API access', 'White-label & deep-link SSO', 'Custom workflow integration'],
    cta: 'Contact Sales',
    ctaLink: 'mailto:sales@lynksavvy.com',
    badge: 'Best Value',
    highlight: false,
    micro: '',
  },
]

export default function Pricing() {
  const [currency, setCurrency] = useState<'INR' | 'USD'>('INR')

  return (
    <section id="pricing" className="py-16 sm:py-24 bg-gray-50 scroll-mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">Simple, Transparent Pricing</h2>
        <p className="mt-3 text-gray-600">Start free. Upgrade as you grow. No hidden fees.</p>

        {/* Currency toggle */}
        <div className="mt-6 inline-flex items-center bg-white rounded-full p-1 border border-gray-200">
          <button
            onClick={() => setCurrency('INR')}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${currency === 'INR' ? 'bg-primary-600 text-white' : 'text-gray-600'}`}
          >
            ₹ INR
          </button>
          <button
            onClick={() => setCurrency('USD')}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${currency === 'USD' ? 'bg-primary-600 text-white' : 'text-gray-600'}`}
          >
            $ USD
          </button>
        </div>

        {currency === 'INR' && (
          <p className="mt-3 text-xs text-gray-400">Prices exclusive of 18% GST for Indian customers</p>
        )}

        <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {tiers.map(t => (
            <div
              key={t.name}
              className={`relative bg-white rounded-xl p-8 text-left shadow-sm ${t.highlight ? 'ring-2 ring-primary-500 shadow-md' : 'border border-gray-200'}`}
            >
              {t.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                  {t.badge}
                </span>
              )}
              <h3 className="text-lg font-semibold text-gray-900">{t.name}</h3>
              <p className="text-sm text-gray-500 mt-1">{t.desc}</p>
              <div className="mt-4">
                <span className="text-4xl font-extrabold text-gray-900">
                  {currency === 'INR' ? t.priceINR : t.priceUSD}
                </span>
                <span className="text-gray-500 text-sm">{t.period}</span>
              </div>
              {(currency === 'INR' ? t.yearlyINR : t.yearlyUSD) && (
                <p className="text-xs text-gray-400 mt-1">{currency === 'INR' ? t.yearlyINR : t.yearlyUSD}</p>
              )}
              <ul className="mt-6 space-y-3">
                {t.features.map(f => (
                  <li key={f} className="flex items-start gap-2 text-sm text-gray-600">
                    <span className="text-emerald-500 mt-0.5">✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              <div className="mt-8">
                {t.ctaLink.startsWith('mailto') ? (
                  <a
                    href={t.ctaLink}
                    className="block w-full text-center px-4 py-2.5 text-sm font-medium rounded-md border border-primary-600 text-primary-600 hover:bg-primary-50 transition-colors"
                  >
                    {t.cta}
                  </a>
                ) : (
                  <Link
                    to={t.ctaLink}
                    className={`block w-full text-center px-4 py-2.5 text-sm font-medium rounded-md transition-colors ${
                      t.highlight
                        ? 'bg-primary-600 text-white hover:bg-primary-700'
                        : 'border border-primary-600 text-primary-600 hover:bg-primary-50'
                    }`}
                  >
                    {t.cta}
                  </Link>
                )}
              </div>
              {t.micro && <p className="text-xs text-gray-400 text-center mt-2">{t.micro}</p>}
            </div>
          ))}
        </div>

        <p className="mt-10 text-sm text-gray-500 max-w-2xl mx-auto">
          All plans include: Tamper-proof watermarks, 5-layer verification, hardware-backed signatures,
          offline capture, audit trail, SMS & email notifications.
        </p>
      </div>
    </section>
  )
}
