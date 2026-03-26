import { Link } from 'react-router-dom'

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-gray-200 bg-white">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-gray-900">TrustCapture</Link>
          <Link to="/" className="text-sm text-primary-600 hover:text-primary-700">← Back to Home</Link>
        </div>
      </nav>
      <main className="max-w-4xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-extrabold text-gray-900 mb-2">Privacy Policy</h1>
        <p className="text-sm text-gray-500 mb-8">Last updated: March 26, 2026</p>

        <div className="prose prose-gray max-w-none space-y-6 text-sm text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">1. Introduction</h2>
            <p>LynkSavvy Technologies ("we", "us", "our") operates the TrustCapture platform (trustcapture-web.onrender.com) and the TrustCapture Android application. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our services.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">2. Information We Collect</h2>
            <p className="font-medium mt-4">Account Information</p>
            <p>When you register, we collect: email address, company name, phone number, contact person details, address, city, state, country, website, and industry.</p>
            <p className="font-medium mt-4">Vendor Information</p>
            <p>For vendors registered by clients: name, phone number, email (optional), city, state, country, and device identifiers.</p>

            <p className="font-medium mt-4">Photo & Sensor Data</p>
            <p>When vendors upload photos, we collect: GPS coordinates, barometric pressure, magnetic field readings, accelerometer data, WiFi network identifiers, cell tower identifiers, device signatures, and photo metadata. This data is essential for our verification service.</p>
            <p className="font-medium mt-4">Usage Data</p>
            <p>We automatically collect: IP addresses, browser type, access times, pages viewed, and referring URLs.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">3. How We Use Your Information</h2>
            <p>We use collected information to:</p>
            <ul className="list-disc pl-6 space-y-1 mt-2">
              <li>Provide and maintain our photo verification service</li>
              <li>Verify the authenticity and location of uploaded photos</li>
              <li>Send transactional emails (welcome, verification results, subscription alerts)</li>
              <li>Send SMS for vendor authentication (OTP)</li>
              <li>Generate reports and analytics for clients</li>
              <li>Enforce subscription quotas and billing</li>
              <li>Maintain audit trails for legal defensibility</li>
              <li>Improve and optimize our services</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">4. Data Storage & Security</h2>
            <p>Your data is stored on secure servers hosted by Render (Singapore region) with PostgreSQL databases. Photos are stored via Cloudinary with encrypted transmission. On the Android app, data is encrypted at rest using SQLCipher (AES-256). Photo signatures use hardware-backed keys (Android StrongBox/TEE).</p>
            <p className="mt-2">We implement industry-standard security measures including: encrypted data transmission (TLS), hash-chained audit logs, role-based access control, and tenant data isolation.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">5. Third-Party Services</h2>
            <p>We use the following third-party services:</p>
            <ul className="list-disc pl-6 space-y-1 mt-2">
              <li>Twilio — SMS delivery for vendor OTP authentication</li>
              <li>SendGrid — Transactional email delivery</li>
              <li>Google Maps — Geocoding (address-to-coordinate resolution)</li>
              <li>Razorpay — Payment processing for subscriptions</li>
              <li>Cloudinary — Photo storage and delivery</li>
              <li>Render — Application hosting</li>
              <li>Open-Meteo / NOAA — Environmental data for verification baselines</li>
            </ul>
            <p className="mt-2">Each third-party service has its own privacy policy. We encourage you to review them.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">6. Data Retention</h2>
            <p>We retain your data for as long as your account is active or as needed to provide services. Photo data and audit logs are retained for the duration required by applicable law or your subscription agreement. You may request deletion of your account and associated data by contacting us.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">7. Your Rights</h2>
            <p>Depending on your jurisdiction, you may have the right to: access your personal data, correct inaccurate data, request deletion of your data, object to processing, and data portability. To exercise these rights, contact us at support@lynksavvy.com.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">8. Multi-Tenancy</h2>
            <p>TrustCapture operates as a multi-tenant platform. Each client organization's data (campaigns, vendors, photos, analytics) is fully isolated from other tenants at the database level. White-label tenants may have their own privacy policies that supplement this one.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">9. Changes to This Policy</h2>
            <p>We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new policy on this page and updating the "Last updated" date.</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-gray-900 mt-8 mb-3">10. Contact Us</h2>
            <p>If you have questions about this Privacy Policy, contact us at:</p>
            <p className="mt-2">LynkSavvy Technologies<br />Lucknow, India<br />Email: support@lynksavvy.com</p>
          </section>
        </div>
      </main>
    </div>
  )
}
