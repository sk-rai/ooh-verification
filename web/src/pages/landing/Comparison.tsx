const rows = [
  { feature: 'Location Verification', manual: 'Manual (slow)', basic: 'GPS only (fakeable)', tc: '5-layer multi-sensor' },
  { feature: 'Offline Capture', manual: '✗', basic: '✗', tc: '✓ Encrypted local storage' },
  { feature: 'Tamper-Proof Watermark', manual: '✗', basic: '✗', tc: '✓ Burned into pixels' },
  { feature: 'Audit Trail', manual: 'Paper-based', basic: 'None', tc: 'Cryptographic hash chain' },
  { feature: 'Bulk Operations', manual: '✗', basic: '✗', tc: '✓ CSV upload' },
  { feature: 'Hardware Signatures', manual: '✗', basic: '✗', tc: '✓ StrongBox/TEE' },
  { feature: 'Time-Window Validation', manual: 'Manual', basic: '✗', tc: '✓ Automatic' },
  { feature: 'Reports & Exports', manual: 'Manual', basic: 'Basic', tc: 'PDF, CSV, GeoJSON, Charts' },
]

export default function Comparison() {
  return (
    <section className="py-16 sm:py-24 bg-white">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 text-center">How TrustCapture Compares</h2>
        <div className="mt-10 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 pr-4 font-semibold text-gray-900">Feature</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-500">Manual Review</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-500">Basic GPS Apps</th>
                <th className="text-center py-3 px-4 font-semibold text-primary-600">TrustCapture</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.feature} className="border-b border-gray-100">
                  <td className="py-3 pr-4 text-gray-700 font-medium">{r.feature}</td>
                  <td className="py-3 px-4 text-center text-gray-400">{r.manual}</td>
                  <td className="py-3 px-4 text-center text-gray-400">{r.basic}</td>
                  <td className="py-3 px-4 text-center text-gray-900 font-medium">{r.tc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
