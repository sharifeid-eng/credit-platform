import { useState, useEffect } from 'react';
import { getCompanies } from '../services/api';
import CompanyCard from '../components/CompanyCard';

export default function Home() {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getCompanies()
      .then(data => {
        setCompanies(data);
        setLoading(false);
      })
      .catch(err => {
        setError('Could not connect to backend. Make sure the server is running.');
        setLoading(false);
      });
  }, []);

  return (
    <div className="min-h-screen pt-24 px-6" style={{ backgroundColor: '#0A0F1E' }}>
      <div className="max-w-7xl mx-auto">

        {/* Page header */}
        <div className="mb-10">
          <h1 className="text-3xl font-bold text-white mb-2">
            Portfolio Companies
          </h1>
          <p className="text-sm" style={{ color: '#64748B' }}>
            Select a company to view loan tape analysis and performance dashboards
          </p>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent 
                            rounded-full animate-spin mx-auto mb-3" />
              <div className="text-sm" style={{ color: '#64748B' }}>
                Loading companies...
              </div>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-xl p-6 mb-6"
               style={{ 
                 backgroundColor: '#1F0D0D',
                 border: '1px solid #3F1313'
               }}>
            <div className="text-red-400 font-medium mb-1">Connection Error</div>
            <div className="text-sm text-red-300">{error}</div>
          </div>
        )}

        {/* Companies grid */}
        {!loading && !error && (
          <>
            {companies.length === 0 ? (
              <div className="text-center py-20">
                <div className="text-5xl mb-4">📁</div>
                <div className="text-white font-medium mb-2">No companies found</div>
                <div className="text-sm" style={{ color: '#64748B' }}>
                  Add company folders to the data/ directory to get started
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {companies.map(company => (
                  <CompanyCard key={company.name} company={company} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}