import { useState } from 'react'
import FileUploadZone from './FileUploadZone'
import CSVTemplateButton from './CSVTemplateButton'
import BulkOperationResults from './BulkOperationResults'
import { BulkOperationResponse } from '../types'

interface BulkUploadTabProps {
  templateType: 'campaigns' | 'vendors' | 'assignments'
  onUpload: (file: File) => Promise<BulkOperationResponse>
  title: string
  description: string
  instructions?: string[]
}

export default function BulkUploadTab({
  templateType,
  onUpload,
  title,
  description,
  instructions,
}: BulkUploadTabProps) {
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<BulkOperationResponse | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const handleFileSelect = (file: File) => {
    setSelectedFile(file)
    setResults(null)
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    setUploading(true)
    try {
      const response = await onUpload(selectedFile)
      setResults(response)
      setSelectedFile(null)
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const handleDownloadReport = () => {
    if (!results) return

    const reportLines = [
      'Bulk Upload Report',
      `Total Processed: ${results.created.length + results.errors.length}`,
      `Successful: ${results.created.length}`,
      `Failed: ${results.errors.length}`,
      '',
      'Errors:',
      ...results.errors.map((e) => `Row ${e.row}: ${e.error}`),
    ]

    const blob = new Blob([reportLines.join('\n')], { type: 'text/plain' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `bulk_upload_report_${Date.now()}.txt`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="py-6">
      {/* Header */}
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      </div>

      {/* Instructions */}
      {instructions && instructions.length > 0 && (
        <div className="mb-6 bg-blue-50 border border-blue-200 rounded-md p-4">
          <h4 className="text-sm font-medium text-blue-900 mb-2">Instructions</h4>
          <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
            {instructions.map((instruction, index) => (
              <li key={index}>{instruction}</li>
            ))}
          </ol>
        </div>
      )}

      {/* Template Download */}
      <div className="mb-6">
        <CSVTemplateButton templateType={templateType} />
      </div>

      {/* File Upload */}
      {!results && (
        <div className="mb-6">
          <FileUploadZone onFileSelect={handleFileSelect} disabled={uploading} />
        </div>
      )}

      {/* Selected File Info */}
      {selectedFile && !results && (
        <div className="mb-6 bg-gray-50 border border-gray-200 rounded-md p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <svg className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <div className="ml-3">
                <p className="text-sm font-medium text-gray-900">{selectedFile.name}</p>
                <p className="text-xs text-gray-500">
                  {(selectedFile.size / 1024).toFixed(2)} KB
                </p>
              </div>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => setSelectedFile(null)}
                disabled={uploading}
                className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-50"
              >
                Remove
              </button>
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {results && (
        <BulkOperationResults
          results={results}
          onClose={() => setResults(null)}
          onDownloadReport={handleDownloadReport}
        />
      )}
    </div>
  )
}
