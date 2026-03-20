import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Navigation from '../../components/Navigation';
import PhotoMap from '../../components/Map/PhotoMap';
import api from '../../services/api';

interface PhotoLocation {
  id: string;
  photo_id: string;
  campaign_name: string;
  campaign_code: string;
  vendor_name: string;
  latitude: number;
  longitude: number;
  verification_status: string;
  confidence_score: number;
  captured_at: string;
  thumbnail_url?: string;
  distance_from_expected?: number;
}

interface CampaignLocation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  verification_radius_meters: number;
}

interface Campaign {
  campaign_id: string;
  campaign_code: string;
  name: string;
}

export default function MapViewEnhanced() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [photos, setPhotos] = useState<PhotoLocation[]>([]);
  const [campaignLocations, setCampaignLocations] = useState<CampaignLocation[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPhoto, setSelectedPhoto] = useState<PhotoLocation | null>(null);
  
  const [filters, setFilters] = useState({
    campaign: searchParams.get('campaign') || '',
    status: searchParams.get('status') || '',
    vendor: searchParams.get('vendor') || '',
    dateFrom: searchParams.get('dateFrom') || '',
    dateTo: searchParams.get('dateTo') || '',
  });

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    // Update URL when filters change
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    setSearchParams(params);
  }, [filters]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [photosRes, campaignsRes] = await Promise.all([
        api.get('/photos'),
        api.get('/campaigns'),
      ]);

      setPhotos(photosRes.data.map((p: any) => ({
        ...p,
        id: p.photo_id,
      })));
      setCampaigns(campaignsRes.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load map data');
    } finally {
      setLoading(false);
    }
  };

  const fetchCampaignLocations = async (campaignCode: string) => {
    try {
      const campaign = campaigns.find(c => c.campaign_code === campaignCode);
      if (!campaign) return;

      const response = await api.get(`/campaigns/${campaign.campaign_id}/locations`);
      setCampaignLocations(response.data);
    } catch (err) {
      console.error('Failed to load campaign locations:', err);
    }
  };

  useEffect(() => {
    if (filters.campaign && campaigns.length > 0) {
      fetchCampaignLocations(filters.campaign);
    } else {
      setCampaignLocations([]);
    }
  }, [filters.campaign, campaigns]);

  const filteredPhotos = photos.filter(photo => {
    if (filters.campaign && photo.campaign_code !== filters.campaign) return false;
    if (filters.status && photo.verification_status !== filters.status) return false;
    if (filters.vendor && photo.vendor_name !== filters.vendor) return false;
    if (filters.dateFrom && new Date(photo.captured_at) < new Date(filters.dateFrom)) return false;
    if (filters.dateTo && new Date(photo.captured_at) > new Date(filters.dateTo)) return false;
    return true;
  });

  const handlePhotoClick = (photo: PhotoLocation) => {
    setSelectedPhoto(photo);
    // Optionally navigate to photo details
    // navigate(`/dashboard/photos/${photo.photo_id}`);
  };

  const exportGeoJSON = async () => {
    try {
      const campaign = campaigns.find(c => c.campaign_code === filters.campaign);
      if (!campaign) {
        alert('Please select a campaign first');
        return;
      }

      window.open(`/api/reports/campaigns/${campaign.campaign_code}/geojson`, '_blank');
    } catch (err) {
      alert('Failed to export GeoJSON');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-500';
      case 'flagged':
        return 'bg-yellow-500';
      case 'rejected':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const uniqueVendors = Array.from(new Set(photos.map(p => p.vendor_name))).sort();

  return (
    <div className="min-h-screen bg-gray-100">
      <Navigation />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Header */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Interactive Map View</h2>
            <p className="text-gray-600 mt-1">Visualize photo locations with clustering and filters</p>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Filters */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Campaign</label>
                <select
                  value={filters.campaign}
                  onChange={(e) => setFilters({ ...filters, campaign: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">All Campaigns</option>
                  {campaigns.map((c) => (
                    <option key={c.campaign_id} value={c.campaign_code}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">All Status</option>
                  <option value="verified">Verified</option>
                  <option value="flagged">Flagged</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Vendor</label>
                <select
                  value={filters.vendor}
                  onChange={(e) => setFilters({ ...filters, vendor: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="">All Vendors</option>
                  {uniqueVendors.map((vendor) => (
                    <option key={vendor} value={vendor}>
                      {vendor}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">From Date</label>
                <input
                  type="date"
                  value={filters.dateFrom}
                  onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">To Date</label>
                <input
                  type="date"
                  value={filters.dateTo}
                  onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <div className="text-sm text-gray-600">
                Showing {filteredPhotos.length} of {photos.length} photos
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilters({
                    campaign: '',
                    status: '',
                    vendor: '',
                    dateFrom: '',
                    dateTo: '',
                  })}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
                >
                  Clear Filters
                </button>
                <button
                  onClick={exportGeoJSON}
                  disabled={!filters.campaign}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center"
                >
                  <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Export GeoJSON
                </button>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
              </div>
            </div>
          ) : filteredPhotos.length === 0 ? (
            <div className="bg-white shadow rounded-lg p-6">
              <p className="text-gray-500 text-center py-8">
                No photos match the selected filters.
              </p>
            </div>
          ) : (
            <div className="bg-white shadow rounded-lg overflow-hidden" style={{ height: '600px' }}>
              <PhotoMap
                photos={filteredPhotos}
                campaignLocations={campaignLocations}
                onPhotoClick={handlePhotoClick as any}
              />
            </div>
          )}

          {/* Selected Photo Details */}
          {selectedPhoto && (
            <div className="mt-6 bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Selected Photo</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {selectedPhoto.thumbnail_url && (
                  <div>
                    <img
                      src={selectedPhoto.thumbnail_url}
                      alt="Selected photo"
                      className="w-full h-64 object-cover rounded-lg"
                    />
                  </div>
                )}
                <div className="space-y-3">
                  <div>
                    <span className="text-sm font-medium text-gray-700">Campaign:</span>
                    <p className="text-sm text-gray-900">{selectedPhoto.campaign_name}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-700">Vendor:</span>
                    <p className="text-sm text-gray-900">{selectedPhoto.vendor_name}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-700">Status:</span>
                    <span className={`ml-2 px-2 py-1 text-xs rounded ${getStatusColor(selectedPhoto.verification_status)} text-white`}>
                      {selectedPhoto.verification_status}
                    </span>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-700">Confidence Score:</span>
                    <p className="text-sm text-gray-900">{selectedPhoto.confidence_score}%</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-700">Captured:</span>
                    <p className="text-sm text-gray-900">{new Date(selectedPhoto.captured_at).toLocaleString()}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-700">Location:</span>
                    <p className="text-sm text-gray-900 font-mono">
                      {selectedPhoto.latitude.toFixed(6)}, {selectedPhoto.longitude.toFixed(6)}
                    </p>
                  </div>
                  {selectedPhoto.distance_from_expected !== undefined && (
                    <div>
                      <span className="text-sm font-medium text-gray-700">Distance from Expected:</span>
                      <p className="text-sm text-gray-900">{selectedPhoto.distance_from_expected.toFixed(0)}m</p>
                    </div>
                  )}
                  <button
                    onClick={() => navigate(`/dashboard/photos/${selectedPhoto.photo_id}`)}
                    className="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    View Full Details
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
