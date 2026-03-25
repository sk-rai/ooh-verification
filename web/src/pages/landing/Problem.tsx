const problems = [
  {
    icon: '📍',
    title: 'Spoofed Locations',
    desc: 'Vendors fake GPS or submit photos from wrong locations. No way to verify they were actually there.',
  },
  {
    icon: '🖼️',
    title: 'Recycled & Edited Photos',
    desc: 'Old photos or altered captures submitted as fresh evidence. Manual review can\'t catch it at scale.',
  },
  {
    icon: '⏱️',
    title: 'Timestamp Manipulation',
    desc: 'Fabricated timestamps make it impossible to confirm when work was actually done.',
  },
]

export default function Problem() {
  return (
    <section className="py-16 sm:py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">
          Field Photo Fraud Is a Billion-Dollar Problem
        </h2>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-8">
          {problems.map(p => (
            <div key={p.title} className="bg-white rounded-xl p-8 shadow-sm">
              <div className="text-4xl mb-4">{p.icon}</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{p.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{p.desc}</p>
            </div>
          ))}
        </div>
        <p className="mt-10 text-sm text-gray-500">
          Businesses lose 15–20% of field operation budgets to unverifiable photo submissions.
        </p>
      </div>
    </section>
  )
}
