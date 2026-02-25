import { useState } from 'react';
import { getTabInsight } from '../services/api';

export default function TabInsight({ company, product, snapshot, asOfDate, currency, tab }) {
  const [insight, setInsight] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const data = await getTabInsight(company, product, snapshot, asOfDate, currency, tab);
      setInsight(data.insight);
    } catch {
      setInsight('Unable to generate insight. Please check your API key.');
    }
    setLoading(false);
  };

  return (
    <div className="rounded-xl p-4 flex gap-4 items-start"
         style={{ backgroundColor: '#0D1F1E', border: '1px solid #134040' }}>
      <div className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center mt-0.5"
           style={{ backgroundColor: '#134040' }}>
        <span className="text-sm">🤖</span>
      </div>
      <div className="flex-1 min-w-0">
        {insight ? (
          <p className="text-sm leading-relaxed" style={{ color: '#CBD5E1' }}>{insight}</p>
        ) : (
          <p className="text-sm" style={{ color: '#4B6B69' }}>
            AI insight for this view — click to generate.
          </p>
        )}
      </div>
      <button
        onClick={generate}
        disabled={loading}
        className="flex-shrink-0 text-xs px-3 py-1.5 rounded-lg transition-all font-medium"
        style={{
          backgroundColor: loading ? '#134040' : '#14B8A6',
          color: loading ? '#4B6B69' : '#fff',
          opacity: loading ? 0.8 : 1,
        }}>
        {loading
          ? <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
              Analyzing
            </span>
          : insight ? 'Refresh' : 'Insight'}
      </button>
    </div>
  );
}