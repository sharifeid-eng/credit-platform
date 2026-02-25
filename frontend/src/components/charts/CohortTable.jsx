export default function CohortTable({ cohorts, currency }) {
  if (!cohorts?.length) return null;

  const hasIRR = cohorts.some(c => c.avg_expected_irr !== undefined);

  return (
    <div className="rounded-xl overflow-hidden"
         style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
      <div className="p-6 pb-4">
        <h3 className="text-sm font-semibold text-white">Vintage Cohort Analysis</h3>
        <p className="text-xs mt-1" style={{ color: '#64748B' }}>
          Performance by deal origination month — {currency}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ backgroundColor: '#0A0F1E', borderTop: '1px solid #1B2B5A' }}>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#64748B' }}>Month</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Deals</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Completion</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Purchase Value</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Collected</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Collection Rate</th>
              <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Denial Rate</th>
              {hasIRR && (
                <>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Exp IRR</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Act IRR</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: '#64748B' }}>Spread</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {cohorts.slice(-36).reverse().map((cohort, i) => {
              const spread = hasIRR && cohort.avg_actual_irr !== undefined && cohort.avg_expected_irr !== undefined
                ? cohort.avg_actual_irr - cohort.avg_expected_irr
                : null;

              const collectionColor = cohort.collection_rate >= 90
                ? '#4ADE80' : cohort.collection_rate >= 75
                ? '#F59E0B' : '#EF4444';

              const denialColor = cohort.denial_rate <= 5
                ? '#4ADE80' : cohort.denial_rate <= 10
                ? '#F59E0B' : '#EF4444';

              return (
                <tr key={cohort.month}
                    style={{
                      borderTop: '1px solid #1B2B5A',
                      backgroundColor: i % 2 === 0 ? 'transparent' : '#0D1428'
                    }}>
                  <td className="px-4 py-2.5 font-medium" style={{ color: '#93C5FD' }}>
                    {cohort.month}
                  </td>
                  <td className="px-4 py-2.5 text-right text-white">
                    {cohort.total_deals}
                  </td>
                  <td className="px-4 py-2.5 text-right" style={{ color: '#94A3B8' }}>
                    {cohort.completion_rate}%
                  </td>
                  <td className="px-4 py-2.5 text-right text-white">
                    {(cohort.purchase_value / 1e6).toFixed(2)}M
                  </td>
                  <td className="px-4 py-2.5 text-right text-white">
                    {(cohort.collected / 1e6).toFixed(2)}M
                  </td>
                  <td className="px-4 py-2.5 text-right font-medium"
                      style={{ color: collectionColor }}>
                    {cohort.collection_rate}%
                  </td>
                  <td className="px-4 py-2.5 text-right font-medium"
                      style={{ color: denialColor }}>
                    {cohort.denial_rate}%
                  </td>
                  {hasIRR && (
                    <>
                      <td className="px-4 py-2.5 text-right" style={{ color: '#94A3B8' }}>
                        {cohort.avg_expected_irr !== undefined ? `${cohort.avg_expected_irr}%` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right" style={{ color: '#94A3B8' }}>
                        {cohort.avg_actual_irr !== undefined ? `${cohort.avg_actual_irr}%` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right font-medium"
                          style={{
                            color: spread === null ? '#64748B'
                              : spread >= 0 ? '#4ADE80' : '#EF4444'
                          }}>
                        {spread !== null ? `${spread >= 0 ? '+' : ''}${spread.toFixed(1)}%` : '—'}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}