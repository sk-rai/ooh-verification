const items = [
  { icon: '🌐', title: 'Custom Domains', desc: 'Your own domain (verify.yourcompany.com). Automatic tenant resolution.' },
  { icon: '🎨', title: 'Branded Experience', desc: 'Custom logo, colors, email templates. Your vendors see your brand.' },
  { icon: '🔒', title: 'Tenant Isolation', desc: "Complete data separation. Each org's campaigns, vendors, photos fully isolated." },
  { icon: '🔗', title: 'Deep-Link Integration', desc: 'Integrate into your existing app with deep-link SSO. API-first architecture.' },
]

export default function MultiTenancy() {
  return (
    <section className="py-16 sm:py-24 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">Your Brand, Your Platform</h2>
        <p className="mt-3 text-gray-600">Run TrustCapture as a fully branded solution for your organization.</p>
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {items.map(it => (
            <div key={it.title} className="text-left">
              <div className="text-3xl mb-3">{it.icon}</div>
              <h3 className="text-base font-semibold text-gray-900 mb-2">{it.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{it.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
