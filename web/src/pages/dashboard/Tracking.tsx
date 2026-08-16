import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup } from 'react-leaflet'
import Navigation from '../../components/Navigation'
import api from '../../services/api'
import 'leaflet/dist/leaflet.css'

export default function Tracking() {
  const [summary, setSummary] = useState<any>(null)
  const [selectedTrack, setSelectedTrack] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  })

  useEffect(() => { fetchSummary() }, [dateRange])

  const fetchSummary = async () => {
    setLoading(true)
    try {
      const r = await api.get(`/api/tracks/summary?start_date=${dateRange.start}&end_date=${dateRange.end}`)
      setSummary(r.data)
    } catch { setSummary(null) }
    finally { setLoading(false) }
  }

  const viewTrack = async (vendorId: string, date: string) => {
    try {
      const r = await api.get(`/api/tracks/vendor/${vendorId}?date=${date}`)
      setSelectedTrack(r.data)
    } catch { setSelectedTrack(null) }
  }

  const trackPoints = selectedTrack?.points || []
  const polyline = trackPoints.filter((p: any) => p.lat && p.lon).map((p: any) => [p.lat, p.lon])
  const center: [number, number] = polyline.length > 0 ? polyline[0] : [20, 78]

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">GPS Tracking</h2>
            <p className="text-gray-600 mt-1">Vendor field attendance and route visualization</p>
          </div>

          {/* Date Filter */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                <input type="date" value={dateRange.start} onChange={(e) => setDateRange({...dateRange, start: e.target.value})} className="rounded-md border-gray-300 shadow-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
                <input type="date" value={dateRange.end} onChange={(e) => setDateRange({...dateRange, end: e.target.value})} className="rounded-md border-gray-300 shadow-sm" />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Map */}
            <div className="lg:col-span-2">
              <div className="bg-white shadow rounded-lg overflow-hidden">
                <MapContainer center={center} zoom={polyline.length > 0 ? 14 : 5} style={{ height: '500px', width: '100%' }} scrollWheelZoom={true}>
                  <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  {polyline.length > 0 && (
                    <>
                      <Polyline positions={polyline} pathOptions={{ color: '#3b82f6', weight: 3 }} />
                      {trackPoints.filter((p: any) => p.lat && p.lon).map((p: any, i: number) => (
                        <CircleMarker key={i} center={[p.lat, p.lon]} radius={5} pathOptions={{ color: i === 0 ? '#22c55e' : i === trackPoints.length - 1 ? '#ef4444' : '#3b82f6', fillOpacity: 0.8 }}>
                          <Popup>
                            <div className="text-xs">
                              <p>Time: {p.timestamp_ms ? new Date(p.timestamp_ms).toLocaleTimeString() : '-'}</p>
                              <p>Accuracy: {p.accuracy || '-'}m</p>
                              {p.battery_pct && <p>Battery: {p.battery_pct}%</p>}
                            </div>
                          </Popup>
                        </CircleMarker>
                      ))}
                    </>
                  )}
                </MapContainer>
                {selectedTrack && selectedTrack.stats && (
                  <div className="p-4 bg-blue-50 border-t">
                    <p className="text-sm"><strong>{selectedTrack.vendor_id}</strong> on {selectedTrack.date}</p>
                    <p className="text-sm text-gray-600">
                      {selectedTrack.stats.start_time?.substring(11,19) || '-'} → {selectedTrack.stats.end_time?.substring(11,19) || '-'} |
                      {selectedTrack.stats.duration_hours}h | {selectedTrack.stats.distance_km} km | {selectedTrack.point_count} points
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Attendance Table */}
            <div className="lg:col-span-1">
              <div className="bg-white shadow rounded-lg p-4">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Attendance Log</h3>
                {loading ? <p className="text-gray-500 text-center py-4">Loading...</p> : (
                  <div className="space-y-2 max-h-[450px] overflow-y-auto">
                    {summary?.rows?.length === 0 && <p className="text-gray-500 text-center py-4">No tracking data yet</p>}
                    {(summary?.rows || []).map((row: any, i: number) => (
                      <button key={i} onClick={() => viewTrack(row.vendor_id, row.date)}
                        className={`w-full text-left p-3 rounded-lg border transition ${selectedTrack?.date === row.date && selectedTrack?.vendor_id === row.vendor_id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="text-sm font-medium">{row.vendor_name || row.vendor_id}</p>
                            <p className="text-xs text-gray-500">{row.date}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-medium">{row.duration_hours}h</p>
                            <p className="text-xs text-gray-500">{row.distance_km} km</p>
                          </div>
                        </div>
                        <div className="mt-1 text-xs text-gray-400">
                          {row.start_time || '-'} → {row.end_time || '-'} | {row.point_count} pings
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
