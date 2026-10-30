import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'

/**
 * /use-cases — multi-vertical overview page.
 * Covers every workflow where photographic field evidence matters.
 * Uses only implemented TrustCapture capabilities.
 * Does NOT claim to replace specialised NDT/inspection-management software.
 */

const VERTICALS = [
  {
    id: 'ooh',
    icon: '🏙️',
    industry: 'OOH Advertising',
    headline: 'Prove every billboard was installed, on time, at the right location.',
    problem:
      'Agencies and media owners pay for placements they cannot independently verify. Field vendors submit recycled or edited photos; disputed installations are costly and slow to resolve.',
    outcome: [
      'Geofence verification — only photos within the campaign radius are accepted.',
      'Gallery-upload blocked — captures must be live, from the field.',
      'Timestamp + GPS watermark burned into every image.',
      'Vendor attendance and GPS route logged per day.',
      'PDF / CSV / GeoJSON campaign reports ready for client review.',
    ],
    useCase: 'A billboard client assigns 40 vendor locations across Mumbai. Each field agent uploads a live capture per site. The dashboard shows verified, flagged and rejected counts in real time; the client receives a signed PDF on campaign close.',
  },
  {
    id: 'insurance',
    icon: '🏠',
    industry: 'Insurance Claims',
    headline: 'Authenticated damage evidence from the first report to settlement.',
    problem:
      'Insurers and third-party administrators receive edited or reused photos with fabricated metadata. Manual review cannot scale to claims volume, and disputes extend settlement timelines.',
    outcome: [
      'Photos signed with a hardware-backed device key — not transferable between devices.',
      'GPS, barometric pressure and magnetic-field readings captured at the moment of capture.',
      'Tamper-evident hash chain across all evidence records.',
      'Multi-location campaign model supports property surveys and re-inspections.',
      'Site-visit reports with timestamps for audit and dispute resolution.',
    ],
    useCase: 'A field adjuster or policyholder captures damage photos through the TrustCapture app. Each image is signed on-device, GPS-located and sensor-validated. The claims team reviews verified evidence in the dashboard with a confidence score and full audit trail — no manual verification required.',
  },
  {
    id: 'industrial',
    icon: '🏗️',
    industry: 'Industrial & Field Inspection',
    headline: 'Verified evidence for QA/QC, construction and infrastructure inspection.',
    problem:
      'Project managers and clients cannot confirm that inspectors visited the right assets, at the right time, and documented what they actually found. Paper and email-based evidence lacks integrity.',
    outcome: [
      'Campaign locations map to specific assets, sites or GPS coordinates — no street address required.',
      'Geofence types: circle, bounding-box, polygon or corridor — configurable per asset.',
      'Asset ID field links each capture to a work order or asset number.',
      'Multi-day, multi-location campaigns track inspection progress across complex sites.',
      'GPS route and attendance proof shows field movement and site coverage.',
    ],
    useCase: 'A construction client creates a campaign with 12 site locations. Each inspector uploads photos at their assigned locations; the system rejects captures taken outside the location geofence. Progress, outstanding inspections and verification outcomes are visible in real time.',
    note: 'TrustCapture is a field-evidence capture and verification platform. It does not replace specialised inspection-management, NDT reporting or asset-lifecycle software.',
  },
  {
    id: 'delivery',
    icon: '🚚',
    industry: 'Delivery & Logistics',
    headline: "Tamper-proof proof-of-delivery that closes disputes before they escalate.",
    problem:
      '"Item not received" disputes drain logistics operations. Delivery agents submit photos from the wrong address or on the wrong day; customers and operations teams have no way to verify.',
    outcome: [
      '150 m geofence for delivery variability while confirming the correct address.',
      'Barometric pressure validates the correct floor in multi-storey buildings.',
      'Offline-first capture — photos stored encrypted on-device and synced when connected.',
      'Chronological audit trail per delivery attempt.',
      'Export evidence per delivery for customer-service and dispute teams.',
    ],
    useCase: 'A last-mile operator assigns a bulk campaign from a CSV with 200 delivery addresses. Each driver uploads a photo on delivery. Operations can filter by verified / flagged and export a CSV of disputed deliveries with the associated evidence.',
  },
  {
    id: 'survey',
    icon: '🌾',
    industry: 'Agriculture & Field Survey',
    headline: 'Remote field verification at survey accuracy for crop, land and asset documentation.',
    problem:
      'Field agents submit survey photos without visiting remote plots. Insurance and subsidy programmes cannot validate ground-truth data at scale, leading to fraudulent or inaccurate claims.',
    outcome: [
      'Coordinate-only locations — no street address needed for rural or remote sites.',
      'Sensor baselines (pressure, magnetic field) compared against Open-Meteo and NOAA data for the location.',
      'Tremor analysis confirms hand-held capture, not a mounted or automated device.',
      'Bulk CSV setup creates hundreds of survey points in one import.',
      'Coverage dashboard shows visited, pending and flagged survey points.',
    ],
    useCase: 'An agricultural insurance provider creates a campaign with 300 plot coordinates. Field agents upload photos at each location; the system auto-validates GPS proximity, sensor context and device integrity. The provider exports verified records for claims processing.',
  },
  {
    id: 'kyb',
    icon: '🏢',
    industry: 'Business Verification & Credentialing',
    headline: 'Verify business premises and operational presence with authenticated visual evidence.',
    problem:
      'KYB and onboarding processes depend on submitted photos that can be staged, recycled or edited. Manual review cannot reliably detect fabricated or misrepresented business premises.',
    outcome: [
      'Live capture only — gallery uploads blocked, preventing reuse of existing images.',
      'GPS, WiFi network scan and cell-tower data corroborate the stated address.',
      'Hardware-backed device signatures prevent cross-device evidence transfer.',
      'Campaign-free Quick Capture for unscheduled or spontaneous verification requests.',
      'Full audit trail per submission for compliance and review teams.',
    ],
    useCase: 'A lending or compliance team initiates a premises verification. The field agent or applicant opens the TrustCapture app and captures the required photos on-site. The reviewer sees GPS-verified, sensor-corroborated evidence with a confidence score — without travelling to the site.',
  },
]

const CAPABILITIES = [
  { name: 'GPS geofence verification', detail: 'Circle, bounding-box, polygon and corridor types' },
  { name: 'Multi-sensor corroboration', detail: 'Barometric pressure, magnetic field, tremor/hand-capture analysis' },
  { name: 'Hardware-backed device signing', detail: 'ECDSA-P256 via Android StrongBox / TEE — key never leaves the device' },
  { name: 'Tamper-evident audit trail', detail: 'Hash-chained, append-only record across all evidence' },
  { name: 'Offline-first capture', detail: 'AES-encrypted on-device storage; auto-syncs when connected' },
  { name: 'Multi-location campaigns', detail: 'Assign multiple GPS or address locations per campaign' },
  { name: 'GPS route and attendance', detail: 'Daily vendor route recording and site-visit summary' },
  { name: 'Bulk CSV setup', detail: 'Create campaigns, vendors and locations in a single import' },
  { name: 'PDF / CSV / GeoJSON reports', detail: 'Export evidence records and site-visit summaries' },
]

export default function UseCases() {
  return (
    <div className="min-h-screen bg-white">
      <Helmet>
        <title>Use Cases — Authenticated Field Evidence for Every Industry | TrustCapture</title>
        <meta
          name="description"
          content="TrustCapture delivers GPS-verified, sensor-validated, cryptographically signed field evidence for OOH advertising, insurance claims, industrial inspection, delivery, agriculture and business verification."
        />
        <link rel="canonical" href="https://app.trustcaptures.com/use-cases" />
        <meta property="og:title" content="Use Cases — Authenticated Field Evidence for Every Industry | TrustCapture" />
        <meta property="og:description" content="From billboard proof to damage claims and field inspections — wherever photographic evidence matters, TrustCapture makes it tamper-proof." />
        <meta property="og:url" content="https://app.trustcaptures.com/use-cases" />
        <meta property="og:image" content="https://app.trustcaptures.com/og-image.png" />
        <script type="application/ld+json">{JSON.stringify({
          "@context": "https://schema.org",
          "@type": "ItemList",
          "name": "TrustCapture Use Cases",
          "description": "Industries where TrustCapture provides authenticated field evidence",
          "itemListElement": VERTICALS.map((v, i) => ({
            "@type": "ListItem",
            "position": i + 1,
            "name": v.industry,
            "description": v.headline,
          })),
        })}</script>
      </Helmet>

      {/* Nav */}
      <nav className="sticky top-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="text-xl font-bold text-gray-900">TrustCapture</Link>
            <div className="flex items-center gap-4">
              <Link to="/" className="hidden sm:block text-sm text-gray-500 hover:text-gray-900">← Back to home</Link>
              <Link to="/register" className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition">
                Start free trial
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <header className="bg-gradient-to-b from-blue-50 to-white py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-blue-600 font-semibold text-sm tracking-wide uppercase mb-3">Use Cases</p>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 leading-tight mb-4">
            Authenticated field evidence<br className="hidden sm:block" /> wherever it matters
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Every industry that relies on photographic proof faces the same problem: submitted photos can be faked, recycled or altered. TrustCapture makes field evidence tamper-proof at the point of capture — GPS-verified, sensor-validated and cryptographically signed.
          </p>
        </div>
      </header>

      {/* Vertical sections */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-20">
        {VERTICALS.map((v, i) => (
          <section key={v.id} id={v.id} className={`grid grid-cols-1 lg:grid-cols-2 gap-10 items-start ${i % 2 === 1 ? 'lg:flex-row-reverse' : ''}`}>
            {/* Left: problem + outcome */}
            <div>
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{v.icon}</span>
                <span className="text-sm font-semibold text-blue-600 uppercase tracking-wide">{v.industry}</span>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-3">{v.headline}</h2>
              <p className="text-gray-600 mb-5">{v.problem}</p>
              <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-3">How TrustCapture helps</h3>
              <ul className="space-y-2">
                {v.outcome.map((o, j) => (
                  <li key={j} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-blue-500 mt-0.5 flex-shrink-0">✓</span>
                    {o}
                  </li>
                ))}
              </ul>
              {v.note && (
                <p className="mt-4 text-xs text-gray-400 italic border-l-2 border-gray-200 pl-3">{v.note}</p>
              )}
            </div>
            {/* Right: scenario card */}
            <div className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Example workflow</p>
              <p className="text-gray-700 text-sm leading-relaxed">{v.useCase}</p>
            </div>
          </section>
        ))}

        {/* Shared capabilities */}
        <section className="border-t border-gray-200 pt-16">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">One platform. Every workflow.</h2>
            <p className="text-gray-600">The same verified-capture foundation powers every vertical.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {CAPABILITIES.map((c) => (
              <div key={c.name} className="bg-blue-50 rounded-xl p-4 border border-blue-100">
                <p className="font-semibold text-gray-900 text-sm mb-1">{c.name}</p>
                <p className="text-gray-600 text-xs">{c.detail}</p>
              </div>
            ))}
          </div>
        </section>

        {/* FAQ */}
        <section className="border-t border-gray-200 pt-16 max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">Frequently asked questions</h2>
          <div className="space-y-6">
            {[
              {
                q: 'Does TrustCapture work offline?',
                a: 'Yes. The Android app stores photos in an AES-encrypted local database and syncs automatically when connectivity is restored. No captures are lost in the field.',
              },
              {
                q: 'Can field agents use their own phones?',
                a: 'Any Android 8.0 or later device works. The app uses StrongBox hardware security on newer devices and falls back to the device TEE on older ones.',
              },
              {
                q: 'How does the geofence work for remote or rural locations?',
                a: 'Locations can be defined by coordinates alone — no street address required. Geofence types include circle, bounding-box, polygon and corridor, configurable per location within a campaign.',
              },
              {
                q: 'Can we set up large numbers of locations quickly?',
                a: 'Yes. The bulk CSV import creates campaigns, vendors and site locations together in one operation. Campaigns, vendors and assignments can also be set up separately via their own CSV templates.',
              },
              {
                q: 'Is there an API for integration into existing workflows?',
                a: 'A stateless verification API with API-key authentication exists and is on the active development roadmap for hardening. Contact us to discuss integration requirements.',
              },
              {
                q: 'Does TrustCapture replace our inspection-management or NDT reporting software?',
                a: 'No. TrustCapture is a field-evidence capture and verification platform. It produces GPS-verified, sensor-validated, signed photographic evidence records and exports. Integration with specialist inspection, NDT or asset-lifecycle systems is the intended deployment model for those workflows.',
              },
            ].map(({ q, a }) => (
              <div key={q} className="border-b border-gray-100 pb-5">
                <p className="font-semibold text-gray-900 mb-1">{q}</p>
                <p className="text-gray-600 text-sm">{a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="bg-blue-600 rounded-2xl px-8 py-12 text-center">
          <h2 className="text-2xl font-bold text-white mb-2">See TrustCapture for your workflow</h2>
          <p className="text-blue-100 mb-6">Start free — no credit card required. Or get in touch to discuss your use case.</p>
          <div className="flex flex-col sm:flex-row justify-center gap-3">
            <Link to="/register" className="inline-flex items-center justify-center px-6 py-3 bg-white text-blue-600 font-semibold rounded-lg hover:bg-blue-50 transition">
              Start free trial
            </Link>
            <a href="mailto:sales@lynksavvy.com" className="inline-flex items-center justify-center px-6 py-3 border border-blue-400 text-white font-semibold rounded-lg hover:bg-blue-700 transition">
              Contact sales →
            </a>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-16 py-8 text-center text-sm text-gray-400">
        <div className="flex flex-wrap justify-center gap-4 mb-2">
          <Link to="/" className="hover:text-gray-600">Home</Link>
          <Link to="/privacy" className="hover:text-gray-600">Privacy</Link>
          <Link to="/terms" className="hover:text-gray-600">Terms</Link>
          <a href="mailto:support@lynksavvy.com" className="hover:text-gray-600">Contact</a>
        </div>
        <p>© 2026 LynkSavvy Technologies, Lucknow, India.</p>
      </footer>
    </div>
  )
}
