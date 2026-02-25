import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="p-3 rounded-lg text-xs"
         style={{ backgroundColor: '#0D1428', border: '1px solid #1B2B5A' }}>
      <div className="font-medium text-white mb-2">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {p.value.toFixed(1)}%
        </div>
      ))}
    </div>
  );
};

export default function DenialTrendChart({ data }) {
  if (!data?.length) return null;

  const chartData = data.slice(-24);

  return (
    <div className="rounded-xl p-6"
         style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-white">Denial Rate Trend</h3>
        <p className="text-xs mt-1" style={{ color: '#64748B' }}>
          Monthly denial rate with 3-month rolling average
        </p>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 20 }}>
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
            tickFormatter={v => `${v}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: '11px', color: '#94A3B8', paddingTop: '16px' }}
          />
          <Bar dataKey="denial_rate" name="Denial Rate"
               fill="#EF4444" opacity={0.7} radius={[2, 2, 0, 0]} />
          <Line
            type="monotone"
            dataKey="denial_rate_3m_avg"
            name="3M Average"
            stroke="#F59E0B"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}