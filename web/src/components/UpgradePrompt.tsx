interface UpgradePromptProps {
  feature: string
  className?: string
}

export default function UpgradePrompt({ feature, className = '' }: UpgradePromptProps) {
  return (
    <div className={`bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-8 text-center ${className}`}>
      <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-blue-100 mb-4">
        <svg
          className="h-8 w-8 text-blue-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
          />
        </svg>
      </div>

      <h3 className="text-lg font-medium text-gray-900 mb-2">
        Upgrade to Access {feature}
      </h3>

      <p className="text-sm text-gray-600 mb-6 max-w-md mx-auto">
        {feature} is available on PRO and ENTERPRISE plans. Upgrade your subscription to unlock this powerful feature and save time managing your campaigns.
      </p>

      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <button
          onClick={() => window.location.href = '/pricing'}
          className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 shadow-sm"
        >
          View Plans
        </button>
        <button
          onClick={() => window.location.href = 'mailto:sales@trustcapture.com'}
          className="inline-flex items-center justify-center px-6 py-3 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
        >
          Contact Sales
        </button>
      </div>

      <div className="mt-6 pt-6 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          PRO and ENTERPRISE plans include bulk uploads, advanced analytics, priority support, and more.
        </p>
      </div>
    </div>
  )
}
