import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getFramework } from '../services/api'
import useBreakpoint from '../hooks/useBreakpoint'

const SECTIONS = [
  { id: 'hierarchy', title: 'Analytical Hierarchy' },
  { id: 'tape-vs-portfolio', title: 'Tape vs Portfolio' },
  { id: 'asset-classes', title: 'Asset Class Adaptations' },
  { id: 'indicators', title: 'Leading vs Lagging' },
  { id: 'separation', title: 'Separation Principle' },
  { id: 'metric-definitions', title: 'Metric Definitions' },
]

export default function Framework() {
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState(SECTIONS[0].id)
  const { isMobile } = useBreakpoint()

  useEffect(() => {
    getFramework()
      .then(md => { setContent(md); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!content) return
    const visibleIds = new Set()
    const observer = new IntersectionObserver(
      entries => {
        for (const e of entries) {
          if (e.isIntersecting) visibleIds.add(e.target.id)
          else visibleIds.delete(e.target.id)
        }
        const first = SECTIONS.find(s => visibleIds.has(s.id))
        if (first) setActive(first.id)
      },
      { rootMargin: '-56px 0px -40% 0px', threshold: 0 },
    )
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [content])

  const scrollTo = id => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (loading) return (
    <div style={{ padding: 40, color: 'var(--text-muted)', textAlign: 'center' }}>
      Loading framework...
    </div>
  )

  return (
    <div style={{ display: 'flex', minHeight: 'calc(100vh - var(--navbar-height))' }}>
      {/* Sidebar TOC — hidden on mobile */}
      {!isMobile && <nav style={{
        width: 220,
        flexShrink: 0,
        position: 'sticky',
        top: 'var(--navbar-height)',
        height: 'calc(100vh - var(--navbar-height))',
        overflowY: 'auto',
        padding: '28px 0 28px 28px',
        borderRight: '1px solid var(--border)',
      }}>
        <Link to="/" style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 12, color: 'var(--gold)', textDecoration: 'none',
          marginBottom: 20, fontWeight: 600,
        }}>
          &larr; Home
        </Link>
        <div style={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--text-muted)',
          marginBottom: 16,
        }}>
          Framework
        </div>
        {SECTIONS.map(s => (
          <button
            key={s.id}
            onClick={() => scrollTo(s.id)}
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px 12px',
              borderLeft: `2px solid ${active === s.id ? 'var(--gold)' : 'transparent'}`,
              color: active === s.id ? 'var(--gold)' : 'var(--text-muted)',
              fontSize: 13,
              fontWeight: active === s.id ? 600 : 400,
              transition: 'all var(--transition-fast)',
              marginBottom: 2,
            }}
          >
            {s.title}
          </button>
        ))}
      </nav>}

      {/* Main content */}
      <div style={{
        flex: 1,
        padding: isMobile ? '20px 14px 40px' : '32px 40px 80px',
        maxWidth: 900,
      }}>
        <h1 style={{
          fontSize: 28,
          fontWeight: 800,
          color: 'var(--text-primary)',
          marginBottom: 8,
          letterSpacing: '-0.02em',
        }}>
          Analysis Framework
        </h1>
        <p style={{
          fontSize: 14,
          color: 'var(--text-muted)',
          marginBottom: 36,
          lineHeight: 1.6,
        }}>
          The analytical philosophy that guides every metric, chart, and AI insight in Laith.
          This document defines the hierarchy of analysis, how metrics differ between Tape and
          Portfolio views, and how each asset class adapts the common framework.
        </p>

        {/* Section 1: Analytical Hierarchy */}
        <Section id="hierarchy" title="1. Analytical Hierarchy">
          <p style={styles.text}>
            Every metric maps to one of five levels. Each level builds on the one below it.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, margin: '20px 0' }}>
            {[
              { level: '1', name: 'Size & Composition', question: 'What do we own?', color: 'var(--blue)', examples: 'Total deals, originated, outstanding, product mix, counterparty count' },
              { level: '2', name: 'Cash Conversion', question: 'How fast does capital return?', color: 'var(--teal)', examples: 'Collection rate, DSO, DTFC, collection timing distribution, pacing' },
              { level: '3', name: 'Credit Quality', question: 'What is deteriorating?', color: 'var(--gold)', examples: 'PAR 30+/60+/90+, health status, roll rates, cure rates, underwriting drift' },
              { level: '4', name: 'Loss Attribution', question: 'Where did the dollars go?', color: 'var(--red)', examples: 'Gross/net default rates, recovery rates, loss waterfall, EL model, LGD' },
              { level: '5', name: 'Forward Signals', question: 'What is about to happen?', color: '#A78BFA', examples: 'DTFC trend, roll rate trajectory, behavioral signals, HHI trend, seasonality' },
            ].map(l => (
              <div key={l.level} style={{
                display: 'flex', gap: 16, alignItems: 'flex-start',
                background: 'var(--bg-surface)', borderRadius: 10,
                padding: '16px 20px', border: '1px solid var(--border)',
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: l.color, opacity: 0.15,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, position: 'relative',
                }}>
                  <span style={{
                    position: 'absolute', fontSize: 16, fontWeight: 800,
                    color: l.color,
                  }}>{l.level}</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: l.color }}>{l.name}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>{l.question}</span>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>{l.examples}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Section 2: Tape vs Portfolio */}
        <Section id="tape-vs-portfolio" title="2. Tape Analytics vs Portfolio Analytics">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 20, margin: '16px 0' }}>
            <div style={styles.card}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--gold)', marginBottom: 8 }}>
                Tape Analytics
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                <strong>Audience:</strong> Investment committee, fund manager<br />
                <strong>Purpose:</strong> Retrospective performance evaluation<br />
                <strong>Source:</strong> Point-in-time CSV/Excel snapshots<br />
                <strong>Horizon:</strong> Entire portfolio history<br />
                <strong>Principle:</strong> Metrics hide when data insufficient — never estimate without clear labeling
              </div>
            </div>
            <div style={styles.card}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--teal)', marginBottom: 8 }}>
                Portfolio Analytics
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                <strong>Audience:</strong> Portfolio manager, facility lender<br />
                <strong>Purpose:</strong> Real-time exposure monitoring<br />
                <strong>Source:</strong> PostgreSQL database (live)<br />
                <strong>Horizon:</strong> Current state<br />
                <strong>Principle:</strong> Conservative — when in doubt, report the more cautious figure
              </div>
            </div>
          </div>
          <p style={styles.text}>
            The same metric can mean different things in each context. PAR 30+ in Tape Analytics
            signals book quality for IC review. PAR 30+ in Portfolio Analytics directly affects the
            advance rate and facility headroom. The denominator differs accordingly: active outstanding
            for Tape, eligible outstanding for Portfolio.
          </p>
        </Section>

        {/* Section 3: Asset Class Adaptations */}
        <Section id="asset-classes" title="3. Asset Class Adaptations">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 20, margin: '16px 0' }}>
            <div style={styles.card}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--gold)', marginBottom: 8 }}>
                Klaim — Healthcare Receivables
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                <strong>Financed:</strong> Insurance claims purchased at discount<br />
                <strong>Obligor:</strong> Insurance companies<br />
                <strong>Default:</strong> Insurance denial of claim<br />
                <strong>Recovery:</strong> Resubmission, appeal, partial collection<br />
                <strong>PAR method:</strong> Expected till date or empirical benchmarks<br />
                <strong>No traditional DPD</strong> — insurance processes on own timeline
              </div>
            </div>
            <div style={styles.card}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--blue)', marginBottom: 8 }}>
                SILQ — POS Lending (KSA)
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                <strong>Financed:</strong> Consumer POS purchases<br />
                <strong>Obligor:</strong> Consumer borrowers<br />
                <strong>Default:</strong> Loan delinquency (DPD-based)<br />
                <strong>Recovery:</strong> Collections, legal enforcement<br />
                <strong>PAR method:</strong> Direct from DPD columns<br />
                <strong>Traditional DPD</strong> — contractual repayment schedules
              </div>
            </div>
          </div>
        </Section>

        {/* Section 4: Leading vs Lagging */}
        <Section id="indicators" title="4. Leading vs Lagging Indicators">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, margin: '16px 0' }}>
            {[
              {
                type: 'Lagging', color: 'var(--text-muted)',
                desc: 'Confirm what already happened',
                items: ['Collection rate', 'Net loss rate', 'Completed margins', 'Cumulative denials'],
              },
              {
                type: 'Coincident', color: 'var(--gold)',
                desc: 'Show what is happening now',
                items: ['PAR 30+/60+/90+', 'Health distribution', 'Outstanding by bucket', 'Current HHI'],
              },
              {
                type: 'Leading', color: 'var(--teal)',
                desc: 'Predict what will happen',
                items: ['DTFC trend', 'Roll rate trajectory', 'Behavioral signals', 'Underwriting drift', 'HHI trend'],
              },
            ].map(g => (
              <div key={g.type} style={styles.card}>
                <div style={{ fontSize: 14, fontWeight: 700, color: g.color, marginBottom: 8 }}>{g.type}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, fontStyle: 'italic' }}>{g.desc}</div>
                {g.items.map(i => (
                  <div key={i} style={{ fontSize: 12, color: 'var(--text-muted)', padding: '3px 0' }}>
                    &bull; {i}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Section>

        {/* Section 5: Separation Principle */}
        <Section id="separation" title="5. The Separation Principle">
          <p style={styles.text}>
            Performance metrics should not be contaminated by fully resolved loss events.
            The platform separates the portfolio into two populations:
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 20, margin: '16px 0' }}>
            <div style={{ ...styles.card, borderColor: 'var(--teal)', borderWidth: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--teal)', marginBottom: 8 }}>
                Clean Portfolio
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                Active deals + normally completed deals. Excludes written-off / fully denied deals.
                Used for collection rate, revenue, ageing, deployment, and most KPIs.
              </div>
            </div>
            <div style={{ ...styles.card, borderColor: 'var(--red)', borderWidth: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--red)', marginBottom: 8 }}>
                Loss Portfolio
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                Deals with denial &gt; 50% of purchase value (Klaim) or charged-off loans (SILQ).
                Analyzed in Loss Waterfall, Recovery Analysis, and Loss Categorization.
              </div>
            </div>
          </div>
          <p style={styles.text}>
            A "Clean Portfolio / Full Portfolio" toggle allows analysts to see both views.
            The default is the full (combined) view for backward compatibility.
          </p>
        </Section>

        {/* Section 6: Metric Definitions */}
        <Section id="metric-definitions" title="6. Key Metric Definitions">
          {[
            {
              name: 'PAR (Portfolio at Risk)',
              formula: 'Outstanding on deals past due X+ days / Total Active Outstanding',
              notes: 'Tape: active outstanding denominator. Portfolio: eligible outstanding. Primary method uses Expected till date; Option C derives empirical benchmarks from completed deals (min 50 deals, labeled "Derived"). Hidden when neither available.',
            },
            {
              name: 'DSO Capital',
              formula: 'Cash-weighted avg days from Deal date to collection',
              notes: 'Measures how long capital is deployed. Curve-based when available.',
            },
            {
              name: 'DSO Operational',
              formula: 'Cash-weighted avg days from expected due date to collection',
              notes: 'Measures operational delay beyond expected timeline.',
            },
            {
              name: 'DTFC (Days to First Cash)',
              formula: 'Median / P90 of days from origination to first collection',
              notes: 'Leading indicator. Uses curve columns when available.',
            },
            {
              name: 'Gross Default Rate',
              formula: 'Denied (or charged-off) amount / Originated per vintage',
              notes: 'Per-vintage metric. Lifetime rates in Loss Waterfall, not as PAR.',
            },
            {
              name: 'Net Loss Rate',
              formula: '(Gross Default - Recovery) / Originated per vintage',
              notes: 'The true economic loss after all recovery efforts.',
            },
            {
              name: 'Recovery Rate',
              formula: 'Recovered post-default / Gross Default',
              notes: 'Tracks how much is recovered from defaulted deals.',
            },
            {
              name: 'EL (Expected Loss)',
              formula: 'PD x LGD x EAD',
              notes: 'PD from completed deal outcomes, LGD from defaulted deals, EAD from active outstanding.',
            },
            {
              name: 'HHI',
              formula: 'Sum of (market share)^2 across groups',
              notes: '< 1,500 = low, 1,500-2,500 = moderate, > 2,500 = concentrated.',
            },
            {
              name: 'Collection Rate',
              formula: 'Collected till date / Purchase Value',
              notes: 'Monthly trend + cumulative. Denominator is face value, not funded amount.',
            },
          ].map(m => (
            <div key={m.name} style={{
              padding: '14px 0',
              borderBottom: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                {m.name}
              </div>
              <div style={{
                fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--gold)',
                marginBottom: 6, padding: '4px 8px', background: 'var(--bg-deep)',
                borderRadius: 4, display: 'inline-block',
              }}>
                {m.formula}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                {m.notes}
              </div>
            </div>
          ))}
        </Section>
      </div>
    </div>
  )
}

function Section({ id, title, children }) {
  return (
    <section id={id} style={{ marginBottom: 40, scrollMarginTop: 72 }}>
      <h2 style={{
        fontSize: 20,
        fontWeight: 700,
        color: 'var(--text-primary)',
        marginBottom: 12,
        paddingBottom: 8,
        borderBottom: '1px solid var(--border)',
        letterSpacing: '-0.01em',
      }}>
        {title}
      </h2>
      {children}
    </section>
  )
}

const styles = {
  text: {
    fontSize: 13,
    color: 'var(--text-muted)',
    lineHeight: 1.7,
    marginBottom: 12,
  },
  card: {
    background: 'var(--bg-surface)',
    borderRadius: 10,
    padding: '16px 20px',
    border: '1px solid var(--border)',
  },
}
