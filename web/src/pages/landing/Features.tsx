const features = [
  { icon: '🔒', title: 'Tamper-Proof Watermarks', desc: 'GPS, timestamp, vendor ID burned into pixels. Any edit visibly corrupts the image — no forensic tools needed.' },
  { icon: '🛡️', title: 'Multi-Sensor Fraud Detection', desc: 'GPS + pressure + magnetic field + tremor + cryptographic signature. Spoofing one sensor is easy — spoofing five is practically impossible.' },
  { icon: '🔐', title: 'Bank-Level Security', desc: 'Photos signed with hardware-backed keys (Android StrongBox/TEE). Private key never leaves the device.' },
  { icon: '📡', title: 'Zero Data Loss in the Field', desc: 'Photos encrypted locally (AES-256). Background sync uploads automatically when connected. Works in remote areas.' },
  { icon: '🌍', title: 'Setup Locations in Seconds', desc: 'Enter address or coordinates — auto-resolved both ways. Pressure and magnetic baselines auto-populated. No manual config.' },
  { icon: '📊', title: 'Actionable Reports', desc: 'PDF, CSV, GeoJSON exports. Charts, map views, vendor performance, time-series analytics — all in your dashboard.' },
  { icon: '📦', title: 'Built for Scale', desc: 'Upload campaigns, vendors, assignments via CSV. Download templates. Process hundreds of records in seconds.' },
  { icon: '⚖️', title: 'Legally Defensible Proof', desc: 'Hash-chained, append-only audit trail. Flags rooted devices, emulators, GPS spoofing. Court-admissible documentation.' },
]

export default function Features() {
  return (
    <section id="features" className="py-16 sm:py-20 bg-white scroll-mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">
          Everything You Need for Trustworthy Field Photos
        </h2>
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map(f => (
            <div key={f.title} className="bg-gray-50 rounded-xl p-6 text-left hover:shadow-md transition-shadow">
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="text-base font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
