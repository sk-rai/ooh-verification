import { BulkOperationResponse } from '../types'

interface BulkOperationResultsProps {
  results: BulkOperationResponse
  onClose: () => void
  onDownloadReport?: () => void
}

export default function BulkOperationResults({ results, onClose, onDownloadReport }: BulkOperationResultsProps) {
  const hasErrors = results.errors.length > 0
  const successCount = results.created.length
  const errorCount = results.errors.length
  const totalProcessed = successCount + errorCount

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Upload Results</h3>
          <p className="mt-1 text-sm text-gray-500">
            Processed {totalProcessed} row{totalProcessed !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-500"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-green-50 rounded-lg p-4">
          <div className="flex items-center">
            <svg className="h-8 w-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="ml-3">
              <p className="text-sm font-medium text-green-800">Successful</p>
              <p className="text-2xl font-bold text-green-900">{successCount}</p>
            </div>
          </div>
        </div>

        <div className={`${hasErrors ? 'bg-red-50' : 'bg-gray-50'} rounded-lg p-4`}>
          <div className="flex items-center">
            <svg
              className={`h-8 w-8 ${hasErrors ? 'text-red-500' : 'text-gray-400'}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="ml-3">
              <p className={`text-sm font-medium ${hasErrors ? 'text-red-800' : 'text-gray-600'}`}>Failed</p>
              <p className={`text-2xl font-bold ${hasErrors ? 'text-red-900' : 'text-gray-700'}`}>{errorCount}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Error Details */}
      {hasErrors && (
        <div className="mb-6">
          <h4 className="text-sm font-medium text-gray-900 mb-2">Errors</h4>
          <div className="bg-red-50 border border-red-200 rounded-md max-h-60 overflow-y-auto">
            <ul className="divide-y divide-red-200">
              {results.errors.map((error, index) => (
                <li key={index} className="p-3">
                  <div className="flex items-start">
                    <span className="flex-shrink-0 text-xs font-medium text-red-700 bg-red-100 rounded px-2 py-1">
                      Row {error.row}
                    </span>
                    <p className="ml-3 text-sm text-red-800">{error.error}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Success Message */}
      {successCount > 0 && (
        <div className="mb-6 bg-green-50 border border-green-200 rounded-md p-4">
          <div className="flex">
            <svg className="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <div className="ml-3">
              <p className="text-sm font-medium text-green-800">
                Successfully created {successCount} record{successCount !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end space-x-3">
        {onDownloadReport && (
          <button
            onClick={onDownloadReport}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Download Report
          </button>
        )}
        <button
          onClick={onClose}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
        >
          Close
        </button>
      </div>
    </div>
  )
}
