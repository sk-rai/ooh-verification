const steps = [
  { num: '1', title: 'OTP Login', desc: 'First login via SMS (Twilio). No passwords.' },
  { num: '2', title: 'Device Registration', desc: 'Hardware key pair generated on-device. Public key sent to server.' },
  { num: '3', title: 'Subsequent Logins', desc: 'Challenge-response with hardware key. No SMS cost.' },
  { num: '4', title: 'Photo Capture', desc: 'Camera-only (gallery blocked). GPS, pressure, magnetic, accelerometer collected at capture time.' },
  { num: '5', title: 'Offline Storage', desc: 'Encrypted local database (SQLCipher). Nothing lost if connectivity drops.' },
  { num: '6', title: 'Background Sync', desc: 'WorkManager handles upload with retry. Verified server-side on upload.' },
]

export default function AndroidApp() {
  return (
    <section className="py-16 sm:py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900">Purpose-Built Android App for Field Workers</h2>
          <p className="mt-3 text-gray-600">Minimal friction, maximum security. Capture and go.</p>
        </div>

        <div className="mt-12 lg:grid lg:grid-cols-2 lg:gap-16 items-start">
          {/* Timeline */}
          <div className="space-y-6">
            {steps.map(s => (
              <div key={s.num} className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-sm font-bold">
                  {s.num}
                </div>
                <div>
                  <h3 className="text-base font-semibold text-gray-900">{s.title}</h3>
                  <p className="text-sm text-gray-600 mt-1">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Phone mockup */}
          <div className="hidden lg:flex justify-center mt-8 lg:mt-0">
            <div className="w-64 h-[480px] bg-gradient-to-br from-gray-800 to-gray-900 rounded-[2rem] p-3 shadow-xl">
              <div className="w-full h-full bg-white rounded-[1.5rem] flex flex-col items-center justify-center space-y-4 p-6">
                <div className="text-5xl">📸</div>
                <div className="w-full space-y-3">
                  <div className="bg-emerald-50 rounded-lg p-3 flex items-center gap-2">
                    <span className="text-emerald-500 text-sm">📍</span>
                    <span className="text-xs text-gray-700">GPS: 26.8467°N, 80.9462°E</span>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3 flex items-center gap-2">
                    <span className="text-blue-500 text-sm">🌡️</span>
                    <span className="text-xs text-gray-700">Pressure: 1012.3 hPa</span>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-3 flex items-center gap-2">
                    <span className="text-purple-500 text-sm">🧲</span>
                    <span className="text-xs text-gray-700">Magnetic: 47.2 µT</span>
                  </div>
                  <div className="bg-amber-50 rounded-lg p-3 flex items-center gap-2">
                    <span className="text-amber-500 text-sm">🔐</span>
                    <span className="text-xs text-gray-700">Signed: StrongBox</span>
                  </div>
                </div>
                <div className="w-full bg-primary-600 text-white text-center py-2 rounded-lg text-sm font-medium">
                  Capture & Sign
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap justify-center gap-4 text-sm text-gray-500">
          <span className="bg-white px-4 py-2 rounded-full border border-gray-200">📱 Android app available for sideloading</span>
          <span className="bg-white px-4 py-2 rounded-full border border-gray-200">🏪 Play Store listing coming soon</span>
          <span className="bg-white px-4 py-2 rounded-full border border-gray-200">🍎 iOS coming soon</span>
        </div>
      </div>
    </section>
  )
}
