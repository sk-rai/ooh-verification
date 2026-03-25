import { Link } from 'react-router-dom'

export default function CTABanner() {
  return (
    <section className="py-16 sm:py-20 bg-primary-600">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
          Ready to Eliminate Field Photo Fraud?
        </h2>
        <p className="mt-4 text-lg text-primary-100">
          Join our early adopter program. Start verifying photos in minutes.
        </p>
        <div className="mt-8">
          <Link
            to="/register"
            className="inline-flex items-center px-8 py-3 text-base font-medium text-primary-600 bg-white hover:bg-primary-50 rounded-md shadow-sm transition-colors"
          >
            Start Free Trial
          </Link>
        </div>
        <p className="mt-3 text-sm text-primary-200">No credit card required. Free tier available forever.</p>
      </div>
    </section>
  )
}
