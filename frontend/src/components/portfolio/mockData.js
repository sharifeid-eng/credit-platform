// Mock data for Portfolio Analytics — will be replaced with real API data in Phase 2

export const MOCK_BORROWING_BASE = {
  waterfall: [
    { label: 'Total A/R',              value: 198_600_000, type: 'total' },
    { label: 'Ineligible A/R',         value: -32_400_000, type: 'deduction' },
    { label: 'Eligible A/R',           value: 166_200_000, type: 'subtotal' },
    { label: 'Concentration Adj.',     value: -8_100_000,  type: 'deduction' },
    { label: 'Advance Rate Discount',  value: -24_930_000, type: 'deduction' },
    { label: 'Borrowing Base',         value: 133_170_000, type: 'result' },
  ],
  kpis: {
    total_ar:         198_600_000,
    eligible_ar:      166_200_000,
    borrowing_base:   133_170_000,
    available_to_draw: 53_170_000,
    ineligible:        32_400_000,
    facility_limit:    80_000_000,
  },
  advance_rates: [
    { region: 'Abu Dhabi', rate: 0.85, eligible_ar: 42_000_000, advanceable: 35_700_000 },
    { region: 'Dubai',     rate: 0.80, eligible_ar: 98_000_000, advanceable: 78_400_000 },
    { region: 'Sharjah',   rate: 0.75, eligible_ar: 26_200_000, advanceable: 19_650_000 },
  ],
  facility: {
    limit:       80_000_000,
    outstanding: 26_830_000,
    available:   53_170_000,
    headroom_pct: 66.5,
  },
}

export const MOCK_CONCENTRATION_LIMITS = [
  { name: 'Single Receivable Limit',         current: 0.047,  threshold: 0.10,  compliant: true,  unit: '%',    format: 'pct' },
  { name: 'Top 5 Provider Concentration',    current: 0.31,   threshold: 0.40,  compliant: true,  unit: '%',    format: 'pct' },
  { name: 'Weighted Avg Life of Receivables', current: 42,     threshold: 60,    compliant: true,  unit: 'days', format: 'days' },
  { name: 'Single Obligor Limit',            current: 0.12,   threshold: 0.15,  compliant: true,  unit: '%',    format: 'pct' },
  { name: 'Healthcare Sector Concentration', current: 1.0,    threshold: 0.80,  compliant: false, unit: '%',    format: 'pct' },
  { name: 'Government Payer Concentration',  current: 0.22,   threshold: 0.35,  compliant: true,  unit: '%',    format: 'pct' },
]

export const MOCK_COVENANTS = [
  {
    name: 'Minimum Consolidated Cash Balance',
    current: 2_400_000,
    threshold: 2_000_000,
    compliant: true,
    operator: '>=',
    unit: 'AED',
    format: 'money',
    period: '2026-02-01 — 2026-02-28',
    breakdown: [
      { label: 'Operating Account Balance', value: 1_800_000 },
      { label: 'Reserve Account Balance',   value: 600_000 },
      { label: 'Total Cash',                value: 2_400_000, bold: true },
    ],
  },
  {
    name: 'PAR30 (Portfolio at Risk > 30 days)',
    current: 0.052,
    threshold: 0.10,
    compliant: true,
    operator: '<=',
    unit: '%',
    format: 'pct',
    period: '2026-02-01 — 2026-02-28',
    breakdown: [
      { label: 'Past Due > 30 Days', value: 10_300_000 },
      { label: 'Total A/R',          value: 198_600_000 },
      { label: 'PAR30 Ratio',        value: 0.052, bold: true },
    ],
  },
  {
    name: 'Collection Ratio',
    current: 0.943,
    threshold: 0.85,
    compliant: true,
    operator: '>=',
    unit: '%',
    format: 'pct',
    period: '2026-02-01 — 2026-02-28',
    breakdown: [
      { label: 'Collections (period)',  value: 624_100_000 },
      { label: 'Expected (period)',     value: 661_800_000 },
      { label: 'Collection Ratio',     value: 0.943, bold: true },
    ],
  },
  {
    name: 'Paid vs Due Ratio',
    current: 0.89,
    threshold: 0.80,
    compliant: true,
    operator: '>=',
    unit: '%',
    format: 'pct',
    period: '2026-02-01 — 2026-02-28',
    breakdown: [
      { label: 'Paid (period)',  value: 524_300_000 },
      { label: 'Due (period)',   value: 589_100_000 },
      { label: 'Paid vs Due',   value: 0.89, bold: true },
    ],
  },
]
