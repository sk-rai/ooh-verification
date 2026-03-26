import { Link } from 'react-router-dom'

export default function TermsOfService() {
  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-gray-200 bg-white">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-gray-900">TrustCapture</Link>
          <Link to="/" className="text-sm text-primary-600 hover:text-primary-700">← Back to Home</Link>
        </div>
      </nav>
      <main className="max-w-4xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-extrabold text-gray-900 mb-2">Terms of Service</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: March 26, 2026</p>

        <div className="prose prose-gray max-w-none space-y-6 text-sm text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">1. Acceptance of Terms</h2>
            <p>By accessing or using TrustCapture (the "Service"), operated by LynkSavvy Technologies ("we", "us"), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">2. Description of Service</h2>
            <p>TrustCapture is a tamper-proof photo verification platform for field operations. The Service includes:</p>
            <ul className="list-disc pl-6 space-y-1 mt-2">
              <li>A web dashboard for campaign management, vendor management, and analytics</li>
              <li>An Android application for field photo capture and verification</li>
              <li>APIs for integration with third-party systems</li>
              <li>Email and SMS notification services</li>
            </ul>
          </section>


          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">3. Account Registration</h2>
            <p>To use the Service, you must register an account with accurate and complete information. You are responsible for maintaining the confidentiality of your account credentials and for all activities under your account. You must notify us immediately of any unauthorized use.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">4. Subscription Plans & Billing</h2>
            <p>The Service offers Free, Pro, and Enterprise subscription tiers. Free accounts are subject to usage limits (photos, vendors, campaigns, storage). Paid subscriptions are billed monthly or annually via Razorpay. Prices are listed in INR and USD on our pricing page.</p>
            <p className="mt-2">You may upgrade or downgrade your plan at any time. Downgrades take effect at the end of the current billing period. Refunds are handled on a case-by-case basis — contact support@lynksavvy.com.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">5. Acceptable Use</h2>
            <p>You agree not to:</p>
            <ul className="list-disc pl-6 space-y-1 mt-2">
              <li>Use the Service for any unlawful purpose</li>
              <li>Attempt to circumvent the verification system (GPS spoofing, photo manipulation, etc.)</li>
              <li>Upload content that infringes intellectual property rights</li>
              <li>Interfere with or disrupt the Service or its infrastructure</li>
              <li>Reverse engineer, decompile, or disassemble any part of the Service</li>
              <li>Share account credentials or allow unauthorized access</li>
              <li>Use automated tools to scrape or extract data from the Service</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">6. Data Ownership</h2>
            <p>You retain ownership of all data you upload to the Service (photos, campaign data, vendor information). We do not claim ownership of your content. However, you grant us a limited license to process, store, and transmit your data as necessary to provide the Service.</p>
            <p className="mt-2">We may generate anonymized, aggregated statistics from usage data for service improvement. Such data will not identify you or your organization.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">7. Verification Accuracy</h2>
            <p>TrustCapture provides photo verification based on multiple sensor inputs (GPS, pressure, magnetic field, device signatures). While our 5-layer verification system is designed to detect fraud with high confidence, we do not guarantee 100% accuracy. Verification results should be used as one factor in your decision-making process, not as the sole determinant.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">8. Service Availability</h2>
            <p>We strive to maintain high availability but do not guarantee uninterrupted access. The Service may be temporarily unavailable due to maintenance, updates, or circumstances beyond our control. We will make reasonable efforts to notify you of planned downtime.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">9. Limitation of Liability</h2>
            <p>To the maximum extent permitted by law, LynkSavvy Technologies shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising from your use of the Service. Our total liability shall not exceed the amount you paid us in the 12 months preceding the claim.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">10. Termination</h2>
            <p>We may suspend or terminate your account if you violate these Terms. You may terminate your account at any time by contacting support@lynksavvy.com. Upon termination, your right to use the Service ceases immediately. We may retain your data for a reasonable period as required by law.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">11. White-Label & Multi-Tenant</h2>
            <p>Enterprise clients using white-label deployments may have supplementary terms specific to their deployment. In case of conflict, the supplementary terms take precedence for that tenant.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">12. Governing Law</h2>
            <p>These Terms are governed by the laws of India. Any disputes shall be subject to the exclusive jurisdiction of the courts in Lucknow, Uttar Pradesh, India.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">13. Changes to Terms</h2>
            <p>We may modify these Terms at any time. We will notify registered users of material changes via email. Continued use of the Service after changes constitutes acceptance of the updated Terms.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">14. Contact</h2>
            <p>For questions about these Terms, contact us at:</p>
            <p className="mt-2">LynkSavvy Technologies<br />Lucknow, India<br />Email: support@lynksavvy.com</p>
          </section>
        </div>
      </main>
    </div>
  )
}
