import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface VendorData {
  vendor_name: string;
  total_photos: number;
  verified: number;
  flagged: number;
  rejected: number;
  verification_rate: number;
}

interface VendorPerformanceChartProps {
  data: VendorData[];
  onBarClick?: (vendor: VendorData) => void;
}

export const VendorPerformanceChart: React.FC<VendorPerformanceChartProps> = ({
  data,
  onBarClick,
}) => {
  const handleClick = (data: any) => {
    if (onBarClick && data) {
      onBarClick(data);
    }
  };

  // Sort by total photos descending
  const sortedData = [...data].sort((a, b) => b.total_photos - a.total_photos);

  return (
    <div className="w-full h-full">
      <div className="text-center mb-4">
        <h3 className="text-lg font-bold text-gray-800">Vendor Performance</h3>
        <p className="text-sm text-gray-600">Photo count and verification rate by vendor</p>
      </div>

      <ResponsiveContainer width="100%" height="85%">
        <BarChart
          data={sortedData}
          margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="vendor_name"
            angle={-45}
            textAnchor="end"
            height={80}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            yAxisId="left"
            orientation="left"
            stroke="#3b82f6"
            tick={{ fontSize: 12 }}
            label={{ value: 'Photo Count', angle: -90, position: 'insideLeft' }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="#10b981"
            tick={{ fontSize: 12 }}
            label={{ value: 'Verification Rate (%)', angle: 90, position: 'insideRight' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '0.5rem',
              padding: '0.5rem',
            }}
            formatter={(value: any, name: string) => {
              if (name === 'verification_rate') {
                return [`${value.toFixed(1)}%`, 'Verification Rate'];
              }
              return [value, name];
            }}
          />
          <Legend />
          <Bar
            yAxisId="left"
            dataKey="total_photos"
            fill="#3b82f6"
            name="Total Photos"
            onClick={handleClick}
            style={{ cursor: onBarClick ? 'pointer' : 'default' }}
          >
            {sortedData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.verification_rate >= 90 ? '#10b981' : entry.verification_rate >= 70 ? '#f59e0b' : '#ef4444'}
              />
            ))}
          </Bar>
          <Bar
            yAxisId="right"
            dataKey="verification_rate"
            fill="#10b981"
            name="Verification Rate"
            onClick={handleClick}
            style={{ cursor: onBarClick ? 'pointer' : 'default' }}
          />
        </BarChart>
      </ResponsiveContainer>

      {/* Performance indicators */}
      <div className="mt-4 flex justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-green-500 rounded"></div>
          <span>≥90% verified</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-yellow-500 rounded"></div>
          <span>70-89% verified</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-red-500 rounded"></div>
          <span>&lt;70% verified</span>
        </div>
      </div>
    </div>
  );
};

export default VendorPerformanceChart;
