export default function KpiCard({ title, value, subtitle, trend, color = 'blue' }) {
  const colors = {
    blue: { accent: '#3B82F6', bg: '#111D3E', border: '#1B2B5A' },
    teal: { accent: '#14B8A6', bg: '#0D1F1E', border: '#134040' },
    red:  { accent: '#EF4444', bg: '#1F0D0D', border: '#3F1313' },
    gold: { accent: '#F59E0B', bg: '#1F1A0D', border: '#3F3213' },
  };

  const c = colors[color] || colors.blue;

  return (
    <div className="rounded-xl p-5 flex flex-col gap-2"
         style={{ 
           backgroundColor: c.bg,
           border: `1px solid ${c.border}`
         }}>
      <div className="text-xs font-medium uppercase tracking-widest"
           style={{ color: '#64748B' }}>
        {title}
      </div>
      <div className="text-2xl font-bold text-white">
        {value}
      </div>
      {subtitle && (
        <div className="text-xs" style={{ color: '#94A3B8' }}>
          {subtitle}
        </div>
      )}
      {trend !== undefined && (
        <div className={`text-xs font-medium ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
        </div>
      )}
      <div className="h-0.5 w-8 rounded mt-1"
           style={{ backgroundColor: c.accent }} />
    </div>
  );
}