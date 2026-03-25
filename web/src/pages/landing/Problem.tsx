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
  {
    icon: '🤖',
    title: 'AI-Generated Fakes',
    desc: 'Generative AI can now create realistic field photos in seconds. Traditional verification is obsolete — you need proof at the moment of capture.',
  },
]

export default function Problem() {
  return (
    <section className="py-16 sm:py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">
          Field Photo Fraud Is a Billion-Dollar Problem
        </h2>
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {problems.map(p => (
            <div key={p.title} className="bg-white rounded-xl p-6 shadow-sm">
              <div className="text-3xl mb-3">{p.icon}</div>
              <h3 className="text-base font-semibold text-gray-900 mb-2">{p.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{p.desc}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-sm text-gray-500">
          Businesses lose 15–20% of field operation budgets to unverifiable photo submissions.
        </p>
      </div>
    </section>
  )
}
