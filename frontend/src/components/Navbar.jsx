import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-navy-700"
         style={{ backgroundColor: '#0D1428' }}>
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
               style={{ backgroundColor: '#3B82F6' }}>
            <span className="text-white font-bold text-sm">ACP</span>
          </div>
          <div>
            <div className="text-white font-semibold text-sm tracking-wide">
              ACP Private Credit
            </div>
            <div className="text-xs" style={{ color: '#60A5FA' }}>
              Portfolio Analytics
            </div>
          </div>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-6">
          <Link to="/" 
                className="text-sm transition-colors"
                style={{ color: '#93C5FD' }}>
            Companies
          </Link>
          <div className="text-sm px-3 py-1.5 rounded-lg"
               style={{ 
                 color: '#60A5FA',
                 backgroundColor: '#111D3E',
                 border: '1px solid #1B2B5A'
               }}>
            v1.0
          </div>
        </div>
      </div>
    </nav>
  );
}