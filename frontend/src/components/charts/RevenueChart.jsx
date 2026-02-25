import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const formatMillions = (value) => {
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toFixed(0);
};

export default function RevenueChart({ data, currency }) {
  if (!data) return null;

  const { monthly, totals } = data;
  const chartData = monthly?.slice(-24) || [];

  return (
    <div className="space-y-4">
      {/* Revenue KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Revenue', value: totals?.gross_revenue, color: '#3B82F6' },
          { label: 'Setup Fees', value: totals?.setup_fees, color: '#14B8A6' },
          { label: 'Other Fees', value: totals?.other_fees, color: '#F59E0B' },
          { label: 'Gross Margin', value: null, pct: totals?.gross_margin, color: '#4ADE80' },
        ].map((item, i) => (
          <div key={i} className="rounded-xl p-4"
               style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
            <div className="text-xs uppercase tracking-wider mb-2" style={{ color: '#64748B' }}>
              {item.label}
            </div>
            <div className="text-xl font-bold" style={{ color: item.color }}>
              {item.pct !== undefined
                ? `${item.pct}%`
                : `${currency} ${formatMillions(item.value || 0)}`}
            </div>
          </div>
        ))}
      </div>

      {/* Monthly revenue chart */}
      <div className="rounded-xl p-6"
           style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-white">Monthly Revenue</h3>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>
            Realised vs unrealised revenue by month — {currency}
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
              yAxisId="left"
              tick={{ fill: '#64748B', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatMillions}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fill: '#64748B', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={v => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0D1428',
                border: '1px solid #1B2B5A',
                fontSize: '11px'
              }}
            />
            <Legend wrapperStyle={{ fontSize: '11px', color: '#94A3B8', paddingTop: '16px' }} />
            <Bar yAxisId="left" dataKey="realised_revenue" name="Realised"
                 stackId="a" fill="#3B82F6" radius={[0, 0, 0, 0]} />
            <Bar yAxisId="left" dataKey="unrealised_revenue" name="Unrealised"
                 stackId="a" fill="#1B2B5A" radius={[3, 3, 0, 0]} />
            <Line yAxisId="right" type="monotone" dataKey="gross_margin"
                  name="Margin %" stroke="#4ADE80" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}