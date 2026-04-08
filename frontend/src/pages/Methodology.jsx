import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useCompany } from '../contexts/CompanyContext'
import { getMethodology } from '../services/api'
import useBreakpoint from '../hooks/useBreakpoint'

// level = Analytical Hierarchy level (see ANALYSIS_FRAMEWORK.md Section 1)
// L1=Size & Composition, L2=Cash Conversion, L3=Credit Quality, L4=Loss Attribution, L5=Forward Signals
const LEVEL_LABELS = {
  1: 'L1', 2: 'L2', 3: 'L3', 4: 'L4', 5: 'L5',
}
const LEVEL_COLORS = {
  1: '#5B8DEF', 2: '#2DD4BF', 3: '#C9A84C', 4: '#F06060', 5: '#A78BFA',
}

export default function Methodology() {
  const { companyName } = useParams()
  const { analysisType } = useCompany()
  const { isMobile } = useBreakpoint()
  const [sections, setSections] = useState([])
  const [active, setActive] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Fetch methodology data from backend
  useEffect(() => {
    if (!analysisType) return
    setLoading(true)
    setError(null)
    getMethodology(analysisType)
      .then(data => {
        setSections(data.sections || [])
        if (data.sections?.length) setActive(data.sections[0].id)
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to load methodology:', err)
        setError('Could not load methodology data.')
        setLoading(false)
      })
  }, [analysisType])

  // Scroll spy: highlight active section in sidebar
  useEffect(() => {
    if (!sections.length) return
    const visibleIds = new Set()
    const observer = new IntersectionObserver(
      entries => {
        for (const e of entries) {
          if (e.isIntersecting) visibleIds.add(e.target.id)
          else visibleIds.delete(e.target.id)
        }
        const first = sections.find(s => visibleIds.has(s.id))
        if (first) setActive(first.id)
      },
      { rootMargin: '-56px 0px -40% 0px', threshold: 0 },
    )
    for (const s of sections) {
      const el = document.getElementById(s.id)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [sections])

  const scrollTo = id => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading methodology...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <div style={{ color: 'var(--accent-red)', fontSize: 13 }}>{error}</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', minHeight: 'calc(100vh - var(--navbar-height))' }}>
      {/* Sidebar TOC — hidden on mobile */}
      {!isMobile && <nav style={{
        width: 220,
        flexShrink: 0,
        position: 'sticky',
        top: 104,
        height: 'calc(100vh - var(--navbar-height))',
        overflowY: 'auto',
        padding: '28px 0 28px 28px',
        borderRight: '1px solid var(--border)',
      }}>
        <div style={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--text-muted)',
          marginBottom: 16,
        }}>
          Contents
        </div>
        {sections.map(s => (
          <button
            key={s.id}
            onClick={() => scrollTo(s.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              width: '100%',
              textAlign: 'left',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px 12px',
              marginBottom: 2,
              fontSize: 11,
              fontWeight: active === s.id ? 600 : 400,
              color: active === s.id ? 'var(--gold)' : 'var(--text-muted)',
              borderLeft: active === s.id ? '2px solid var(--gold)' : '2px solid transparent',
              transition: 'all 0.15s',
              fontFamily: 'var(--font-ui)',
            }}
          >
            {s.title}
            {s.level && (
              <span style={{
                fontSize: 8,
                fontWeight: 700,
                padding: '1px 4px',
                borderRadius: 3,
                backgroundColor: LEVEL_COLORS[s.level] + '18',
                color: LEVEL_COLORS[s.level],
                letterSpacing: '0.04em',
                flexShrink: 0,
              }}>
                {LEVEL_LABELS[s.level]}
              </span>
            )}
          </button>
        ))}
      </nav>}

      {/* Main content */}
      <main style={{ flex: 1, padding: isMobile ? '20px 14px 40px' : '36px 40px 80px', maxWidth: 820 }}>
        {/* Back to dashboard */}
        <Link to={`/company/${companyName}`} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          textDecoration: 'none',
          fontSize: 11, fontWeight: 600,
          color: 'var(--gold)',
          marginBottom: 16,
          transition: 'opacity 0.15s',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5" /><path d="M12 19l-7-7 7-7" />
          </svg>
          Back to {companyName?.toUpperCase()} Dashboard
        </Link>
        <h1 style={{
          fontSize: 26,
          fontWeight: 800,
          letterSpacing: '-0.03em',
          color: 'var(--text-primary)',
          margin: '0 0 6px',
        }}>
          Methodology
        </h1>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 36px', lineHeight: 1.6 }}>
          Definitions, formulas, and rationale for every analytical metric in the platform.
          This page documents <em>how</em> metrics are calculated and <em>why</em> they matter for credit analysis.
        </p>

        {/* Dynamic sections from API */}
        {sections.map(sec => (
          <Section key={sec.id} id={sec.id} title={sec.title}>
            {sec.prose && <p style={styles.body}>{sec.prose}</p>}
            {sec.metrics.map((m, i) => (
              <Metric key={i} name={m.name} formula={m.formula} rationale={m.rationale} />
            ))}
            {sec.tables.map((t, i) => (
              <div key={`t-${i}`}>
                {t.title && <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', margin: '16px 0 8px' }}>{t.title}</h3>}
                <Table headers={t.headers} rows={t.rows} />
              </div>
            ))}
            {sec.notes.map((n, i) => (
              <Note key={`n-${i}`}>{n}</Note>
            ))}
            {sec.subsections?.map((sub, i) => (
              <Subsection key={`sub-${i}`} title={sub.title}>
                {sub.prose && <p style={styles.body}>{sub.prose}</p>}
                {sub.metrics?.map((m, j) => (
                  <Metric key={j} name={m.name} formula={m.formula} rationale={m.rationale} />
                ))}
                {sub.tables?.map((t, j) => (
                  <div key={`st-${j}`}>
                    {t.title && <h4 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', margin: '10px 0 6px' }}>{t.title}</h4>}
                    <Table headers={t.headers} rows={t.rows} />
                  </div>
                ))}
                {sub.notes?.map((n, j) => (
                  <Note key={`sn-${j}`}>{n}</Note>
                ))}
              </Subsection>
            ))}
          </Section>
        ))}
      </main>
    </div>
  )
}


/* ── Reusable sub-components ───────────────────────────────── */

function Section({ id, title, children }) {
  return (
    <section id={id} style={{ marginBottom: 40, scrollMarginTop: 120 }}>
      <h2 style={{
        fontSize: 20,
        fontWeight: 700,
        color: 'var(--text-primary)',
        margin: '0 0 16px',
        paddingBottom: 10,
        borderBottom: '1px solid var(--border)',
      }}>
        {title}
      </h2>
      {children}
    </section>
  )
}

function Subsection({ title, children }) {
  return (
    <div style={{ marginTop: 20, marginBottom: 12 }}>
      <h3 style={{
        fontSize: 14,
        fontWeight: 700,
        color: 'var(--text-primary)',
        margin: '0 0 8px',
      }}>
        {title}
      </h3>
      {children}
    </div>
  )
}

function Metric({ name, formula, rationale }) {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '14px 18px',
      marginBottom: 10,
    }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
        {name}
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: 'var(--gold)',
        background: 'var(--bg-deep)',
        borderRadius: 'var(--radius-sm)',
        padding: '6px 10px',
        marginBottom: 8,
        display: 'inline-block',
      }}>
        {formula}
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.7, color: 'var(--text-muted)' }}>
        {rationale}
      </div>
    </div>
  )
}

function Table({ headers, rows }) {
  return (
    <div style={{ overflowX: 'auto', marginBottom: 12 }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: 12,
      }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{
                textAlign: 'left',
                padding: '8px 10px',
                fontSize: 10,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--text-muted)',
                borderBottom: '1px solid var(--border)',
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} style={{
                  padding: '7px 10px',
                  borderBottom: '1px solid var(--border)',
                  color: ci === 0 ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontWeight: ci === 0 ? 600 : 400,
                  fontFamily: ci === 0 ? 'var(--font-mono)' : 'var(--font-ui)',
                }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Note({ children }) {
  return (
    <div style={{
      fontSize: 11,
      color: 'var(--text-muted)',
      background: 'rgba(201,168,76,0.06)',
      border: '1px solid rgba(201,168,76,0.15)',
      borderRadius: 'var(--radius-sm)',
      padding: '10px 14px',
      marginTop: 8,
      marginBottom: 12,
      lineHeight: 1.7,
    }}>
      {children}
    </div>
  )
}

const styles = {
  body: {
    fontSize: 13,
    lineHeight: 1.7,
    color: 'var(--text-muted)',
    margin: '0 0 12px',
  },
}
