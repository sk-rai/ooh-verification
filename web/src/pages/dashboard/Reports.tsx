import { useState, useEffect } from 'react'
import Navigation from '../../components/Navigation'
import api from '../../services/api'
import Plot from 'react-plotly.js'

interface ReportStats {
  total_photos: number
  verified_photos: number
  failed_photos: number
  pending_photos: number
  total_campaigns: number
  active_campaigns: number
  total_vendors: number
  active_vendors: number
}

interface CampaignStats {
  campaign_name: string
  photo_count: number
  verified_count: number
}

interface VendorStats {
  vendor_name: string
  photo_count: number
  verification_rate: number
}

interface TimeSeriesData {
  date: string
  photo_count: number
}

export default function Reports() {
  const [stats, setStats] = useState<ReportStats | null>(null)
  const [campaignStats, setCampaignStats] = useState<CampaignStats[]>([])
  const [vendorStats, setVendorStats] = useState<VendorStats[]>([])
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  })

  useEffect(() => {
    fetchReportData()
  }, [dateRange])

  const fetchReportData = async () => {
    setLoading(true)
    try {
      const [statsRes, campaignsRes, vendorsRes, timeSeriesRes] = await Promise.all([
        api.get('/api/reports/statistics').catch(() => ({ data: {} })),
        api.get('/api/reports/campaigns').catch(() => ({ data: [] })),
        api.get('/api/reports/vendors').catch(() => ({ data: [] })),
        api.get(`/api/reports/time-series?start=${dateRange.start}&end=${dateRange.end}`).catch(() => ({ data: [] })),
      ])

      setStats(statsRes.data)
      setCampaignStats(campaignsRes.data)
      setVendorStats(vendorsRes.data)
      setTimeSeriesData(timeSeriesRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load report data')
    } finally {
      setLoading(false)
    }
  }

  const exportCSV = async () => {
    try {
      const response = await api.get('/api/reports/export/csv', {
        responseType: 'blob',
        params: { start_date: dateRange.start, end_date: dateRange.end },
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `trustcapture-report-${dateRange.start}-${dateRange.end}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Failed to export CSV')
    }
  }

  const exportPDF = async () => {
    try {
      const response = await api.get('/api/reports/export/pdf', {
        responseType: 'blob',
        params: { start_date: dateRange.start, end_date: dateRange.end },
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `trustcapture-report-${dateRange.start}-${dateRange.end}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Failed to export PDF')
    }
  }

  // Verification Status Pie Chart
  const verificationPieChart = stats ? {
    data: [{
      values: [stats.verified_photos, stats.failed_photos, stats.pending_photos],
      labels: ['Verified', 'Failed', 'Pending'],
      type: 'pie' as const,
      marker: {
        colors: ['#10b981', '#ef4444', '#f59e0b'],
      },
    }],
    layout: {
      title: 'Verification Status Distribution',
      height: 300,
      margin: { t: 40, b: 40, l: 40, r: 40 },
    },
  } : null

  // Campaign Performance Bar Chart
  const campaignBarChart = campaignStats.length > 0 ? {
    data: [{
      x: campaignStats.map(c => c.campaign_name),
      y: campaignStats.map(c => c.photo_count),
      type: 'bar' as const,
      marker: { color: '#3b82f6' },
      name: 'Total Photos',
    }, {
      x: campaignStats.map(c => c.campaign_name),
      y: campaignStats.map(c => c.verified_count),
      type: 'bar' as const,
      marker: { color: '#10b981' },
      name: 'Verified Photos',
    }],
    layout: {
      title: 'Campaign Performance',
      height: 300,
      margin: { t: 40, b: 80, l: 60, r: 40 },
      xaxis: { title: 'Campaign' },
      yaxis: { title: 'Photo Count' },
      barmode: 'group' as const,
    },
  } : null

  // Vendor Performance Chart
  const vendorBarChart = vendorStats.length > 0 ? {
    data: [{
      x: vendorStats.map(v => v.vendor_name),
      y: vendorStats.map(v => v.verification_rate * 100),
      type: 'bar' as const,
      marker: { color: '#8b5cf6' },
    }],
    layout: {
      title: 'Vendor Verification Rate (%)',
      height: 300,
      margin: { t: 40, b: 80, l: 60, r: 40 },
      xaxis: { title: 'Vendor' },
      yaxis: { title: 'Verification Rate (%)', range: [0, 100] },
    },
  } : null

  // Time Series Line Chart
  const timeSeriesChart = timeSeriesData.length > 0 ? {
    data: [{
      x: timeSeriesData.map(d => d.date),
      y: timeSeriesData.map(d => d.photo_count),
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      marker: { color: '#3b82f6' },
      line: { shape: 'spline' as const },
    }],
    layout: {
      title: 'Photos Captured Over Time',
      height: 300,
      margin: { t: 40, b: 60, l: 60, r: 40 },
      xaxis: { title: 'Date' },
      yaxis: { title: 'Photo Count' },
    },
  } : null

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Header */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Reports & Analytics</h2>
            <p className="text-gray-600 mt-1">View insights and export reports</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Date Range & Export */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                <input
                  type="date"
                  value={dateRange.start}
                  onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
                <input
                  type="date"
                  value={dateRange.end}
                  onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={exportCSV}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center"
                >
                  <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Export CSV
                </button>
                <button
                  onClick={exportPDF}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 flex items-center"
                >
                  <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  Export PDF
                </button>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">Loading analytics...</p>
            </div>
          ) : (
            <>
              {/* Summary Stats */}
              {stats && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                  <div className="bg-white overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <dt className="text-sm font-medium text-gray-500 truncate">Total Photos</dt>
                      <dd className="mt-1 text-3xl font-semibold text-gray-900">{stats.total_photos}</dd>
                    </div>
                  </div>
                  <div className="bg-white overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <dt className="text-sm font-medium text-gray-500 truncate">Verified</dt>
                      <dd className="mt-1 text-3xl font-semibold text-green-600">{stats.verified_photos}</dd>
                    </div>
                  </div>
                  <div className="bg-white overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <dt className="text-sm font-medium text-gray-500 truncate">Failed</dt>
                      <dd className="mt-1 text-3xl font-semibold text-red-600">{stats.failed_photos}</dd>
                    </div>
                  </div>
                  <div className="bg-white overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <dt className="text-sm font-medium text-gray-500 truncate">Pending</dt>
                      <dd className="mt-1 text-3xl font-semibold text-yellow-600">{stats.pending_photos}</dd>
                    </div>
                  </div>
                </div>
              )}

              {/* Charts Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Verification Status Pie Chart */}
                {verificationPieChart && (
                  <div className="bg-white shadow rounded-lg p-6">
                    <Plot
                      data={verificationPieChart.data}
                      layout={verificationPieChart.layout}
                      config={{ responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                )}

                {/* Campaign Performance */}
                {campaignBarChart && (
                  <div className="bg-white shadow rounded-lg p-6">
                    <Plot
                      data={campaignBarChart.data}
                      layout={campaignBarChart.layout}
                      config={{ responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                )}

                {/* Vendor Performance */}
                {vendorBarChart && (
                  <div className="bg-white shadow rounded-lg p-6">
                    <Plot
                      data={vendorBarChart.data}
                      layout={vendorBarChart.layout}
                      config={{ responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                )}

                {/* Time Series */}
                {timeSeriesChart && (
                  <div className="bg-white shadow rounded-lg p-6">
                    <Plot
                      data={timeSeriesChart.data}
                      layout={timeSeriesChart.layout}
                      config={{ responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                )}
              </div>

              {/* Empty State */}
              {!stats && campaignStats.length === 0 && (
                <div className="bg-white shadow rounded-lg p-6">
                  <p className="text-gray-500 text-center py-8">
                    No data available for the selected date range.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
