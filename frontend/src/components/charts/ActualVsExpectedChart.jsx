import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
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

export default function ActualVsExpectedChart({ data, currency, totals }) {
  if (!data?.length) return null;

  const performance = totals?.overall_performance || 0;
  const performanceColor = performance >= 95 ? '#4ADE80' : performance >= 85 ? '#F59E0B' : '#EF4444';

  return (
    <div className="rounded-xl p-6"
         style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Actual vs Expected Collections</h3>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>
            Cumulative collected vs expected — {currency}
          </p>
        </div>
        {totals && (
          <div className="flex gap-4 text-right">
            <div>
              <div className="text-xs" style={{ color: '#64748B' }}>Performance</div>
              <div className="text-lg font-bold" style={{ color: performanceColor }}>
                {performance}%
              </div>
            </div>
            <div>
              <div className="text-xs" style={{ color: '#64748B' }}>Collected</div>
              <div className="text-sm font-semibold text-white">
                {currency} {formatMillions(totals.total_collected)}
              </div>
            </div>
            <div>
              <div className="text-xs" style={{ color: '#64748B' }}>Expected</div>
              <div className="text-sm font-semibold" style={{ color: '#64748B' }}>
                {currency} {formatMillions(totals.total_expected)}
              </div>
            </div>
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 20 }}>
          <defs>
            <linearGradient id="collectedGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="expectedGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
            </linearGradient>
          </defs>
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
          <Area
            type="monotone"
            dataKey="cumulative_collected"
            name="Collected"
            stroke="#3B82F6"
            strokeWidth={2}
            fill="url(#collectedGrad)"
          />
          <Area
            type="monotone"
            dataKey="cumulative_expected"
            name="Expected"
            stroke="#F59E0B"
            strokeWidth={2}
            strokeDasharray="5 5"
            fill="url(#expectedGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}