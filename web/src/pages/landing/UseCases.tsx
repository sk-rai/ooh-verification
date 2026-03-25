import { useState } from 'react'

const tabs = [
  {
    id: 'ooh',
    label: '🏙️ OOH Advertising',
    problem: "Agencies can't verify if billboards were installed at the right location and time. With 800+ placements per campaign, manual review is impossible.",
    points: [
      '50m geofence verification — photos outside the boundary are auto-flagged',
      'Forced live capture — gallery uploads blocked, eliminating recycled images',
      'Visible watermark with GPS, timestamp, vendor ID — any edit corrupts it visibly',
      'Campaign code authentication ties every photo to the correct campaign',
      '5-layer confidence score (0–100%) per photo: signature, GPS, pressure, magnetic, tremor',
    ],
  },
  {
    id: 'delivery',
    label: '🚚 Delivery & Logistics',
    problem: '"Item Not Received" disputes cost billions. Delivery agents submit fake proof-of-delivery photos. No verifiable evidence for dispute resolution.',
    points: [
      'Delivery time-window validation — photos outside the expected window are flagged',
      '150m geofence for delivery variability while confirming correct address',
      'Barometric pressure validates correct floor in multi-story buildings',
      'Offline-ready — photos encrypted locally, sync when connected. No deliveries lost.',
      'Hash-chained audit trail — tamper-evident, legally defensible proof for every delivery',
    ],
  },
  {
    id: 'construction',
    label: '🏗️ Construction',
    problem: "Contractors submit progress photos from wrong dates or locations. Remote managers can't verify site conditions. Disputes lack evidence.",
    points: [
      'GPS-locked site documentation — photos must be within geofence to be accepted',
      'Timestamped progress records create an unalterable construction timeline',
      'Altitude verification via barometric pressure — confirms which floor the photo was taken from',
      'Magnetic field fingerprinting cross-references NOAA data for the location',
      'Append-only audit log provides legally defensible documentation for disputes',
    ],
  },
  {
    id: 'agriculture',
    label: '🌾 Agriculture & Survey',
    problem: "Field agents submit survey photos without visiting remote locations. Unverified data leads to fraudulent insurance claims and incorrect assessments.",
    points: [
      'GPS geofencing works in rural areas — sensor data captured at capture time, uploads when connected',
      'Pressure and magnetic readings compared server-side against auto-populated baselines',
      'Tremor analysis confirms photo taken by human hand, not mounted device',
      'Bulk survey campaigns — upload hundreds of locations via CSV, assign agents in bulk',
      'Coverage dashboard shows visited, pending, and flagged survey points',
    ],
  },
]

export default function UseCases() {
  const [active, setActive] = useState('ooh')
  const current = tabs.find(t => t.id === active)!

  return (
    <section id="use-cases" className="py-16 sm:py-24 bg-gray-50 scroll-mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">
            Built for Every Industry That Relies on Field Photos
          </h2>
          <p className="mt-3 text-gray-600">Select your industry to see how TrustCapture addresses your challenges.</p>
        </div>

        {/* Tab buttons */}
        <div className="mt-10 flex flex-wrap justify-center gap-2">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActive(t.id)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                active === t.id
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
              aria-selected={active === t.id}
              role="tab"
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="mt-10 bg-white rounded-xl p-8 shadow-sm max-w-4xl mx-auto" role="tabpanel">
          <p className="text-gray-700 font-medium mb-6">{current.problem}</p>
          <h3 className="text-sm font-semibold text-primary-600 uppercase tracking-wide mb-4">How TrustCapture Helps</h3>
          <ul className="space-y-3">
            {current.points.map((p, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className="mt-1 flex-shrink-0 w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-xs">✓</span>
                <span className="text-sm text-gray-600 leading-relaxed">{p}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
