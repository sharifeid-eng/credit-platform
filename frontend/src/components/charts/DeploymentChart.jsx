import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const formatMillions = (value) => {
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toFixed(0);
};

const CustomTooltip = ({ active, payload, label, currency }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="p-3 rounded-lg text-xs"
         style={{ backgroundColor: '#0D1428', border: '1px solid #1B2B5A' }}>
      <div className="font-medium text-white mb-2">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {currency} {formatMillions(p.value)}
        </div>
      ))}
    </div>
  );
};

export default function DeploymentChart({ data, currency }) {
  if (!data?.length) return null;

  // Show last 24 months
  const chartData = data.slice(-24);

  return (
    <div className="rounded-xl p-6"
         style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-white">Capital Deployed by Month</h3>
        <p className="text-xs mt-1" style={{ color: '#64748B' }}>
          New vs repeat business — {currency}
        </p>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1B2B5A" vertical={false} />
          <XAxis
            dataKey="Month"
            tick={{ fill: '#64748B', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#1B2B5A' }}
            angle={-45}
            textAnchor="end"
            interval={2}
          />
          <YAxis
            tick={{ fill: '#64748B', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatMillions}
          />
          <Tooltip content={<CustomTooltip currency={currency} />} />
          <Legend
            wrapperStyle={{ fontSize: '11px', color: '#94A3B8', paddingTop: '16px' }}
          />
          <Bar dataKey="new_business" name="New Business"
               stackId="a" fill="#3B82F6" radius={[0, 0, 0, 0]} />
          <Bar dataKey="repeat_business" name="Repeat Business"
               stackId="a" fill="#F59E0B" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}