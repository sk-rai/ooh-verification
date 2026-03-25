import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

interface VerificationData {
  verified: number;
  flagged: number;
  rejected: number;
}

interface VerificationPieChartProps {
  data: VerificationData;
  onSliceClick?: (status: string) => void;
}

const COLORS = {
  verified: '#10b981',  // green
  flagged: '#f59e0b',   // yellow
  rejected: '#ef4444',  // red
};

export const VerificationPieChart: React.FC<VerificationPieChartProps> = ({
  data,
  onSliceClick,
}) => {
  const chartData = [
    { name: 'Verified', value: data.verified, status: 'verified' },
    { name: 'Flagged', value: data.flagged, status: 'flagged' },
    { name: 'Rejected', value: data.rejected, status: 'rejected' },
  ].filter(item => item.value > 0); // Only show non-zero values

  const total = data.verified + data.flagged + data.rejected;

  const CustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * Math.PI / 180);
    const y = cy + radius * Math.sin(-midAngle * Math.PI / 180);

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? 'start' : 'end'}
        dominantBaseline="central"
        className="text-sm font-bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  const handleClick = (entry: any) => {
    if (onSliceClick) {
      onSliceClick(entry.status);
    }
  };

  return (
    <div className="w-full h-full">
      <div className="text-center mb-4">
        <h3 className="text-lg font-bold text-gray-800">Verification Status</h3>
        <p className="text-sm text-gray-600">Total Photos: {total}</p>
      </div>
      
      <ResponsiveContainer width="100%" height="85%">
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={CustomLabel}
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
            onClick={handleClick}
            style={{ cursor: onSliceClick ? 'pointer' : 'default' }}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[entry.status as keyof typeof COLORS]}
              />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: any) => [value, 'Photos']}
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '0.5rem',
              padding: '0.5rem',
            }}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value: any, entry: any) => {
              const percentage = ((entry.payload.value / total) * 100).toFixed(1);
              return `${value}: ${entry.payload.value} (${percentage}%)`;
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export default VerificationPieChart;
