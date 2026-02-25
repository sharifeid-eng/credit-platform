import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';

const formatMillions = (value) => {
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toFixed(0);
};

export default function AgeingChart({ data, currency }) {
  if (!data) return null;

  const { health_summary, ageing_buckets, total_active_deals, total_active_value } = data;

  return (
    <div className="space-y-6">
      {/* Health summary */}
      <div className="rounded-xl p-6"
           style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
        <div className="flex items-start justify-between mb-6">
          <div>
            <h3 className="text-sm font-semibold text-white">Portfolio Health</h3>
            <p className="text-xs mt-1" style={{ color: '#64748B' }}>
              Active deals by health status — {total_active_deals?.toLocaleString()} deals
            </p>
          </div>
          <div className="text-right">
            <div className="text-xs" style={{ color: '#64748B' }}>Active Portfolio</div>
            <div className="text-sm font-semibold text-white">
              {currency} {formatMillions(total_active_value)}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Donut chart */}
          <div className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={health_summary}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  dataKey="deal_count"
                  nameKey="status"
                >
                  {health_summary?.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value, name) => [value, name]}
                  contentStyle={{
                    backgroundColor: '#0D1428',
                    border: '1px solid #1B2B5A',
                    fontSize: '11px'
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Health legend */}
          <div className="flex flex-col justify-center gap-3">
            {health_summary?.map((item, i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-sm" style={{ color: '#CBD5E1' }}>{item.status}</span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-medium text-white">{item.deal_count}</span>
                  <span className="text-xs ml-2" style={{ color: item.color }}>
                    {item.percentage}%
                  </span>
                </div>
              </div>
            ))}
            <div className="text-xs mt-2 pt-2" style={{ color: '#64748B', borderTop: '1px solid #1B2B5A' }}>
              Healthy: ≤60 days · Watch: 61-90 · Delayed: 91-120 · Poor: 120+
            </div>
          </div>
        </div>
      </div>

      {/* Ageing buckets */}
      <div className="rounded-xl p-6"
           style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-white">Active Deals by Days Outstanding</h3>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>
            Distribution of open positions by age
          </p>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={ageing_buckets} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
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
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0D1428',
                border: '1px solid #1B2B5A',
                fontSize: '11px'
              }}
            />
            <Bar dataKey="deal_count" name="Deals" fill="#3B82F6" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}