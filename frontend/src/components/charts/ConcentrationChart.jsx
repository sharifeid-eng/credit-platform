import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

const formatMillions = (value) => {
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toFixed(0);
};

const COLORS = [
  '#3B82F6', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#6366F1',
  '#10B981', '#F43F5E', '#0EA5E9', '#A855F7', '#22C55E'
];

function ConcentrationDonut({ data, title, valueKey, labelKey, currency }) {
  if (!data?.length) return null;

  const total = data.reduce((sum, d) => sum + (d[valueKey] || 0), 0);

  return (
    <div className="rounded-xl p-6"
         style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
      <h3 className="text-sm font-semibold text-white mb-4">{title}</h3>
      <div className="flex gap-4">
        <div className="flex-shrink-0">
          <ResponsiveContainer width={160} height={160}>
            <PieChart>
              <Pie
                data={data.slice(0, 10)}
                cx="50%"
                cy="50%"
                innerRadius={45}
                outerRadius={75}
                dataKey={valueKey}
              >
                {data.slice(0, 10).map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v) => [`${currency} ${formatMillions(v)}`, '']}
                contentStyle={{
                  backgroundColor: '#0D1428',
                  border: '1px solid #1B2B5A',
                  fontSize: '10px'
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 overflow-y-auto max-h-40 space-y-1.5">
          {data.slice(0, 10).map((item, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 min-w-0">
                <div className="w-2 h-2 rounded-full flex-shrink-0"
                     style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <span className="truncate" style={{ color: '#CBD5E1' }}>
                  {item[labelKey] || 'Unknown'}
                </span>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                <span style={{ color: '#64748B' }}>
                  {((item[valueKey] / total) * 100).toFixed(1)}%
                </span>
                <span className="text-white font-medium">
                  {formatMillions(item[valueKey])}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TopDealsTable({ deals, currency }) {
  if (!deals?.length) return null;

  return (
    <div className="rounded-xl overflow-hidden"
         style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
      <div className="p-6 pb-4">
        <h3 className="text-sm font-semibold text-white">Top 10 Largest Deals</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ backgroundColor: '#0A0F1E', borderTop: '1px solid #1B2B5A' }}>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#64748B' }}>Date</th>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#64748B' }}>Status</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Purchase Value</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Discount</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Collected</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((deal, i) => (
              <tr key={i}
                  style={{
                    borderTop: '1px solid #1B2B5A',
                    backgroundColor: i % 2 === 0 ? 'transparent' : '#0D1428'
                  }}>
                <td className="px-4 py-2.5" style={{ color: '#93C5FD' }}>
                  {deal['Deal date']?.split('T')[0] || '—'}
                </td>
                <td className="px-4 py-2.5">
                  <span className="px-2 py-0.5 rounded-full text-xs"
                        style={{
                          backgroundColor: deal.Status === 'Completed' ? '#0D2818' : '#1F1A0D',
                          color: deal.Status === 'Completed' ? '#4ADE80' : '#F59E0B',
                          border: `1px solid ${deal.Status === 'Completed' ? '#166534' : '#713F12'}`
                        }}>
                    {deal.Status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right text-white font-medium">
                  {currency} {formatMillions(deal['Purchase value'])}
                </td>
                <td className="px-4 py-2.5 text-right" style={{ color: '#94A3B8' }}>
                  {deal.Discount ? `${(deal.Discount * 100).toFixed(1)}%` : '—'}
                </td>
                <td className="px-4 py-2.5 text-right" style={{ color: '#4ADE80' }}>
                  {deal['Collected till date']
                    ? `${currency} ${formatMillions(deal['Collected till date'])}`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ConcentrationChart({ data, currency }) {
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {data.group && (
          <ConcentrationDonut
            data={data.group}
            title="Concentration by Group"
            valueKey="purchase_value"
            labelKey="Group"
            currency={currency}
          />
        )}
        {data.product && (
          <ConcentrationDonut
            data={data.product}
            title="Concentration by Product"
            valueKey="purchase_value"
            labelKey="Product"
            currency={currency}
          />
        )}
      </div>
      <TopDealsTable deals={data.top_deals} currency={currency} />
    </div>
  );
}