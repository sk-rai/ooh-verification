import { useState } from 'react'

const faqs = [
  {
    q: 'How accurate is the GPS verification?',
    a: 'We use a configurable geofence radius (default 50m for OOH, 150m for delivery). Combined with barometric pressure and magnetic field validation, our 5-layer system catches location spoofing that GPS-only solutions miss.',
  },
  {
    q: 'What happens if vendors have no internet in the field?',
    a: 'The app is offline-first. Photos are captured, signed, and stored in an encrypted local database. They sync automatically when connectivity returns. No data is ever lost.',
  },
  {
    q: 'Can photos be faked with GPS spoofing apps?',
    a: 'GPS spoofing is caught by cross-referencing barometric pressure, magnetic field, and WiFi/cell tower data. Our audit system also flags rooted devices and emulators. Spoofing one sensor is easy — spoofing five simultaneously is practically impossible.',
  },
  {
    q: 'Do vendors need special phones?',
    a: 'Any Android 8.0+ device works. The app uses StrongBox hardware security on newer devices and falls back to TEE on older ones — both are highly secure.',
  },
  {
    q: 'How long does setup take?',
    a: 'Create your first campaign in under 5 minutes. Location baselines (pressure, magnetic field) are auto-populated — no manual configuration needed. Vendors get an SMS with the app link and can start capturing immediately.',
  },
  {
    q: 'Is the data legally defensible?',
    a: 'Yes. Every photo is logged in a hash-chained, append-only audit trail with full sensor data and cryptographic signatures. This creates tamper-evident records suitable for legal proceedings, insurance claims, and regulatory compliance.',
  },
  {
    q: 'Can I use my own branding?',
    a: "Enterprise plans include full white-label support — custom domain, logo, colors, and branded email templates. White-label deployments include custom workflow integration, SSO setup, and dedicated onboarding. Contact sales for pricing.",
  },
  {
    q: 'What does the Android app do?',
    a: "The purpose-built Android app handles the vendor side: OTP login, hardware key registration, camera-only photo capture (gallery blocked), sensor data collection, encrypted local storage, and background sync. Available for sideloading now, Play Store listing coming soon. iOS coming soon.",
  },
  {
    q: 'What services power TrustCapture?',
    a: "We're built on trusted infrastructure: Twilio (SMS), SendGrid (email), Google Maps (geocoding), NOAA World Magnetic Model (magnetic field baselines), Open-Meteo (elevation/pressure), and Razorpay (payments).",
  },
]

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null)

  return (
    <section id="faq" className="py-16 sm:py-24 bg-white scroll-mt-20">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 text-center">Frequently Asked Questions</h2>
        <div className="mt-10 space-y-3">
          {faqs.map((f, i) => (
            <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-gray-50 transition-colors"
                aria-expanded={open === i}
              >
                <span className="text-sm font-medium text-gray-900">{f.q}</span>
                <svg
                  className={`w-5 h-5 text-gray-400 flex-shrink-0 transition-transform ${open === i ? 'rotate-180' : ''}`}
                  fill="none" stroke="currentColor" viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {open === i && (
                <div className="px-6 pb-4">
                  <p className="text-sm text-gray-600 leading-relaxed">{f.a}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
