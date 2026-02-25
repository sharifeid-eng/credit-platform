import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, LineChart, Line, Legend
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
          {p.name}: {p.name.includes('Rate') ? `${p.value}%` : `${currency} ${formatMillions(p.value)}`}
        </div>
      ))}
    </div>
  );
};

export default function CollectionVelocityChart({ data, currency }) {
  if (!data) return null;

  const monthlyData = data.monthly?.slice(-24) || [];

  return (
    <div className="space-y-6">
      {/* Monthly collection rate */}
      <div className="rounded-xl p-6"
           style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-white">Monthly Collection Rate</h3>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>
            Collected as % of purchase value by origination month
          </p>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={monthlyData} margin={{ top: 5, right: 10, left: 10, bottom: 20 }}>
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
              domain={[0, 120]}
            />
            <Tooltip content={<CustomTooltip currency={currency} />} />
            <Line
              type="monotone"
              dataKey="collection_rate"
              name="Collection Rate"
              stroke="#14B8A6"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Collection buckets */}
      <div className="rounded-xl p-6"
           style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-white">Completed Deals by Days Outstanding</h3>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>
            Distribution of collection timing
          </p>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={data.buckets}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1B2B5A" vertical={false} />
            <XAxis
              dataKey="bucket"
              tick={{ fill: '#64748B', fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: '#1B2B5A' }}
            />
            <YAxis
              tick={{ fill: '#64748B', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={v => v.toLocaleString()}
            />
            <Tooltip content={<CustomTooltip currency={currency} />} />
            <Bar dataKey="deal_count" name="Deal Count"
                 fill="#3B82F6" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}