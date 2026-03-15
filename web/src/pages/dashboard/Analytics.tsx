import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import VerificationPieChart from '../../components/Charts/VerificationPieChart';
import TimelineChart from '../../components/Charts/TimelineChart';
import VendorPerformanceChart from '../../components/Charts/VendorPerformanceChart';

interface CampaignStatistics {
  campaign: {
    campaign_code: string;
    name: string;
    start_date: string;
    end_date: string;
  };
  total_photos: number;
  verification_status: {
    verified: number;
    flagged: number;
    rejected: number;
  };
  average_confidence_score: number;
  vendors: Array<{
    vendor_name: string;
    total_photos: number;
    verified: number;
    flagged: number;
    rejected: number;
    verification_rate: number;
  }>;
  timeline: Array<{
    date: string;
    count: number;
    verified: number;
    flagged: number;
    rejected: number;
  }>;
}

export const Analytics: React.FC = () => {
  const { campaignCode } = useParams<{ campaignCode: string }>();
  const navigate = useNavigate();
  const [statistics, setStatistics] = useState<CampaignStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (campaignCode) {
      fetchStatistics();
    }
  }, [campaignCode]);

  const fetchStatistics = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get(`/reports/campaigns/${campaignCode}/statistics`);
      setStatistics(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load statistics');
      console.error('Error fetching statistics:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleVerificationSliceClick = (status: string) => {
    // Navigate to photo gallery with status filter
    navigate(`/dashboard/campaigns/${campaignCode}/photos?status=${status}`);
  };

  const handleVendorClick = (vendor: any) => {
    // Navigate to photo gallery with vendor filter
    navigate(`/dashboard/campaigns/${campaignCode}/photos?vendor=${vendor.vendor_name}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
          <button
            onClick={fetchStatistics}
            className="mt-2 text-red-600 hover:text-red-800 underline"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!statistics) {
    return (
      <div className="p-6">
        <p className="text-gray-600">No statistics available</p>
      </div>
    );
  }

  const verificationRate = (
    (statistics.verification_status.verified / statistics.total_photos) * 100
  ).toFixed(1);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">
              {statistics.campaign.name}
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              Campaign Code: {statistics.campaign.campaign_code}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {new Date(statistics.campaign.start_date).toLocaleDateString()} -{' '}
              {new Date(statistics.campaign.end_date).toLocaleDateString()}
            </p>
          </div>
          <button
            onClick={() => navigate(`/dashboard/campaigns/${campaignCode}`)}
            className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition"
          >
            ← Back to Campaign
          </button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-gray-600">Total Photos</p>
          <p className="text-3xl font-bold text-gray-800 mt-2">
            {statistics.total_photos}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-gray-600">Verification Rate</p>
          <p className="text-3xl font-bold text-green-600 mt-2">
            {verificationRate}%
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-gray-600">Avg Confidence</p>
          <p className="text-3xl font-bold text-blue-600 mt-2">
            {statistics.average_confidence_score.toFixed(0)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-gray-600">Active Vendors</p>
          <p className="text-3xl font-bold text-purple-600 mt-2">
            {statistics.vendors.length}
          </p>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Verification Status Pie Chart */}
        <div className="bg-white rounded-lg shadow p-6" style={{ height: '400px' }}>
          <VerificationPieChart
            data={statistics.verification_status}
            onSliceClick={handleVerificationSliceClick}
          />
        </div>

        {/* Timeline Chart */}
        <div className="bg-white rounded-lg shadow p-6" style={{ height: '400px' }}>
          <TimelineChart data={statistics.timeline} />
        </div>
      </div>

      {/* Vendor Performance Chart */}
      <div className="bg-white rounded-lg shadow p-6" style={{ height: '500px' }}>
        <VendorPerformanceChart
          data={statistics.vendors}
          onBarClick={handleVendorClick}
        />
      </div>

      {/* Export Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-bold text-gray-800 mb-4">Export Data</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => window.open(`/api/reports/campaigns/${campaignCode}/csv`, '_blank')}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
          >
            📊 Export CSV
          </button>
          <button
            onClick={() => window.open(`/api/reports/campaigns/${campaignCode}/pdf`, '_blank')}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
          >
            📄 Export PDF
          </button>
          <button
            onClick={() => window.open(`/api/reports/campaigns/${campaignCode}/geojson`, '_blank')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            🗺️ Export GeoJSON
          </button>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
