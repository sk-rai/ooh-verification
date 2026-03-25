const steps = [
  {
    num: '1',
    icon: '📋',
    title: 'Create Campaign',
    desc: 'Set locations and geofence radius. Enter address or coordinates — auto-resolved both ways. Pressure and magnetic baselines auto-populated. Zero manual config.',
  },
  {
    num: '2',
    icon: '👥',
    title: 'Assign Vendors',
    desc: 'Add workers individually or bulk CSV. Each gets a unique ID and SMS with app download link.',
  },
  {
    num: '3',
    icon: '📱',
    title: 'Capture',
    desc: 'Vendor opens app, enters campaign code, takes photo. GPS, pressure, magnetic field collected automatically. Photo signed with hardware key. Works offline.',
  },
  {
    num: '4',
    icon: '✅',
    title: 'Review',
    desc: 'Dashboard shows verification status and confidence score. Flagged photos highlighted. Export PDF, CSV, GeoJSON. Interactive map view.',
  },
]

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-16 sm:py-24 bg-white scroll-mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">
          From Setup to Verified Results in 4 Steps
        </h2>
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map(s => (
            <div key={s.num} className="relative">
              <div className="flex items-center justify-center w-12 h-12 mx-auto rounded-full bg-primary-100 text-primary-700 font-bold text-lg mb-4">
                {s.num}
              </div>
              <div className="text-3xl mb-3">{s.icon}</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{s.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
