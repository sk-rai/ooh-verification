const integrations = [
  { name: 'Twilio', desc: 'SMS' },
  { name: 'SendGrid', desc: 'Email' },
  { name: 'Google Maps', desc: 'Geocoding' },
  { name: 'NOAA', desc: 'Magnetic Field' },
  { name: 'Open-Meteo', desc: 'Elevation' },
  { name: 'Razorpay', desc: 'Payments' },
]

export default function PoweredBy() {
  return (
    <section className="py-10 bg-gray-50 border-t border-gray-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-4">Built on trusted infrastructure</p>
        <div className="flex flex-wrap justify-center gap-6 sm:gap-10">
          {integrations.map(i => (
            <div key={i.name} className="text-center">
              <p className="text-sm font-semibold text-gray-500">{i.name}</p>
              <p className="text-xs text-gray-400">{i.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
