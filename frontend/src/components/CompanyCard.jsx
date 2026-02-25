import { Link } from 'react-router-dom';

export default function CompanyCard({ company }) {
  return (
    <Link to={`/company/${company.name}`}
          className="block rounded-xl p-6 transition-all duration-200 hover:scale-[1.02]"
          style={{
            backgroundColor: '#111D3E',
            border: '1px solid #1B2B5A',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = '#3B82F6'}
          onMouseLeave={e => e.currentTarget.style.borderColor = '#1B2B5A'}>

      {/* Company header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center"
               style={{ backgroundColor: '#1B2B5A' }}>
            <span className="text-white font-bold text-sm">
              {company.name.substring(0, 2).toUpperCase()}
            </span>
          </div>
          <div>
            <div className="text-white font-semibold">
              {company.name.toUpperCase()}
            </div>
            <div className="text-xs" style={{ color: '#64748B' }}>
              {company.products.length} product{company.products.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
        <div className="text-xs px-2 py-1 rounded-full"
             style={{ 
               backgroundColor: '#0D2818',
               color: '#4ADE80',
               border: '1px solid #166534'
             }}>
          Active
        </div>
      </div>

      {/* Products list */}
      <div className="flex flex-wrap gap-2 mb-4">
        {company.products.map(product => (
          <span key={product}
                className="text-xs px-2 py-1 rounded-md"
                style={{ 
                  backgroundColor: '#0A0F1E',
                  color: '#93C5FD',
                  border: '1px solid #1B2B5A'
                }}>
            {product.replace(/_/g, ' ')}
          </span>
        ))}
      </div>

      {/* Snapshots count */}
      <div className="flex items-center justify-between">
        <div className="text-xs" style={{ color: '#64748B' }}>
          {company.total_snapshots} snapshot{company.total_snapshots !== 1 ? 's' : ''} available
        </div>
        <div className="text-xs" style={{ color: '#3B82F6' }}>
          View Dashboard →
        </div>
      </div>
    </Link>
  );
}