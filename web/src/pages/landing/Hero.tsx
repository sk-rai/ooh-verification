import { Link } from 'react-router-dom'

export default function Hero() {
  return (
    <section className="pt-24 pb-16 sm:pt-32 sm:pb-24 bg-gradient-to-b from-primary-50/40 to-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="lg:grid lg:grid-cols-2 lg:gap-16 items-center">
          <div>
            <p className="text-sm font-medium text-primary-600 mb-4">
              Built for OOH agencies, logistics companies, construction firms, and field survey teams
            </p>
            <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 leading-tight tracking-tight">
              Tamper-Proof Photo Verification for Field Operations
            </h1>
            <p className="mt-6 text-lg text-gray-600 leading-relaxed">
              Prevent fraud at the point of capture. GPS-stamped, sensor-validated,
              cryptographically signed and encrypted at rest — photos your field teams can't fake.
            </p>
            <p className="mt-3 text-sm text-gray-500">
              📱 Available on Android &nbsp;|&nbsp; iOS Coming Soon
            </p>
            <div className="mt-8 flex flex-col sm:flex-row gap-3">
              <Link
                to="/register"
                className="inline-flex justify-center items-center px-6 py-3 text-base font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-md shadow-sm transition-colors"
              >
                Start Free Trial
              </Link>
              <a
                href="#how-it-works"
                className="inline-flex justify-center items-center px-6 py-3 text-base font-medium text-primary-600 bg-white border border-primary-200 hover:bg-primary-50 rounded-md transition-colors"
              >
                See How It Works
              </a>
            </div>
            <p className="mt-3 text-xs text-gray-400">No credit card required. Setup in under 5 minutes.</p>
          </div>

          {/* Right side illustration placeholder */}
          <div className="hidden lg:flex justify-center mt-12 lg:mt-0">
            <div className="w-80 h-96 bg-gradient-to-br from-primary-100 to-primary-50 rounded-3xl flex items-center justify-center shadow-lg">
              <div className="text-center space-y-4 px-8">
                <div className="text-6xl">📱</div>
                <div className="bg-white rounded-xl p-4 shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">GPS Match</span>
                    <span className="text-xs font-semibold text-emerald-600">98.2%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Pressure</span>
                    <span className="text-xs font-semibold text-emerald-600">✓ Valid</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Signature</span>
                    <span className="text-xs font-semibold text-emerald-600">✓ Verified</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Confidence</span>
                    <span className="text-sm font-bold text-primary-600">94%</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500">Verified on upload</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
