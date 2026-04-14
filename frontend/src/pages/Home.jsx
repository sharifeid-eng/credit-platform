import { useEffect, useState } from 'react'
import { useNavigate, Link }                        from 'react-router-dom'
import { motion }                                   from 'framer-motion'
import { getCompanies, getSummary, getSnapshots }   from '../services/api'
import PortfolioStatsHero                           from '../components/PortfolioStatsHero'
import useBreakpoint                                from '../hooks/useBreakpoint'

// ── Derive region + asset class from known company / product names ───────────
function getCompanyMeta(companyName) {
  const n = companyName.toLowerCase()
  if (n.includes('klaim'))  return { countryCode: 'ae', region: 'UAE', assetClass: 'Healthcare Receivables' }
  if (n.includes('silq'))   return { countryCode: 'sa', region: 'KSA', assetClass: 'POS Lending'            }
  if (n.includes('ejari'))  return { countryCode: 'sa', region: 'KSA', assetClass: 'Rent Finance'           }
  if (n.includes('tamara')) return { countryCode: ['sa', 'ae'], region: 'KSA & UAE', assetClass: 'BNPL'     }
  if (n.includes('aajil'))  return { countryCode: 'sa', region: 'KSA', assetClass: 'SME Trade Credit'      }
  return { countryCode: null, region: '', assetClass: '' }
}

// ── Typewriter text (respects prefers-reduced-motion) ───────────────────────
function TypewriterText({ text, speed = 28 }) {
  const [displayed, setDisplayed] = useState('')
  const [done,      setDone]      = useState(false)

  useEffect(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReduced) { setDisplayed(text); setDone(true); return }

    let i = 0
    const timer = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) { clearInterval(timer); setDone(true) }
    }, speed)
    return () => clearInterval(timer)
  }, [text, speed])

  return (
    <p style={{
      fontSize: 15, color: 'var(--text-muted)', margin: 0,
      fontFamily: 'var(--font-ui)', letterSpacing: '0.01em', lineHeight: 1.55,
      minHeight: 24,
    }}>
      {displayed}
      {!done && (
        <span style={{
          color: 'var(--gold)', marginLeft: 1,
          animation: 'twBlink 0.75s step-end infinite',
        }}>|</span>
      )}
      <style>{`@keyframes twBlink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </p>
  )
}

// ── Animated hero accent logo ────────────────────────────────────────────────
function HeroLogo() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.34, 1.56, 0.64, 1] }}
      style={{ flexShrink: 0 }}
    >
      <div style={{
        width: 60, height: 60,
        borderRadius: 14,
        overflow: 'hidden',
        background: '#000',
      }}>
        <img src="/lion.png" alt="Laith" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
      </div>
    </motion.div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function Home() {
  const [companies,  setCompanies]  = useState([])
  const [summaries,  setSummaries]  = useState({})
  const navigate = useNavigate()
  const { isMobile } = useBreakpoint()

  useEffect(() => {
    getCompanies().then(async (data) => {
      const normalized = data.map(c =>
        typeof c === 'string'
          ? { name: c, products: [], total_snapshots: 0, since: null }
          : { name: c.name ?? c.id ?? String(c), products: c.products ?? [], total_snapshots: c.total_snapshots ?? 0, since: c.since ?? null }
      )
      setCompanies(normalized)

      // Fetch summaries in parallel — ALL products, not just first (for multi-product cards)
      const result = {}
      const fetchJobs = normalized.flatMap(co =>
        (co.products || []).map(async product => {
          try {
            const snaps    = await getSnapshots(co.name, product)
            const last     = snaps?.[snaps.length - 1]
            const snapFile = last?.filename ?? last ?? null
            const summary  = await getSummary(co.name, product, snapFile, 'USD')
            result[`${co.name}:${product}`] = summary
          } catch (_) {}
        })
      )
      await Promise.allSettled(fetchJobs)
      setSummaries(result)
    })
  }, [])

  const handleOpen = (co) => {
    const defaultProduct = co.products?.[0] ?? ''
    if (defaultProduct) navigate(`/company/${co.name}/${defaultProduct}/tape/overview`)
    else navigate(`/company/${co.name}`)
  }

  return (
    <div style={{ minHeight: '100vh', position: 'relative' }}>

      {/* ── Islamic geometric background pattern ── */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none',
          backgroundImage: 'url(/geometric-pattern.svg)',
          backgroundRepeat: 'repeat',
          backgroundSize: '140px 140px',
          opacity: 0.14,
        }}
      />

      {/* ── Portfolio stats hero strip ── */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        <PortfolioStatsHero />
      </div>

      {/* ── Main content ── */}
      <div style={{ position: 'relative', zIndex: 1, padding: isMobile ? '24px 14px 40px' : '44px 28px 60px', maxWidth: 1280, margin: '0 auto' }}>

        {/* Hero — logo pulse + headline + typewriter */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          style={{ textAlign: 'center', marginBottom: 48 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20, marginBottom: 14 }}>
            <h1 style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(40px, 5.5vw, 64px)',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              lineHeight: 1,
              background: 'linear-gradient(135deg, #E8C96A 0%, var(--gold) 40%, #A07830 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              margin: 0,
            }}>
              Credit Analytics
            </h1>
          </div>

          <TypewriterText text="GCC asset-backed lending Analytics" />
        </motion.div>

        {/* ── Section label ── */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18,
        }}>
          <span style={{
            fontSize: 13, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.14em', color: 'var(--text-muted)',
          }}>
            Portfolio Companies
          </span>
          <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        </div>

        {/* ── Company grid ── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? '260px' : '320px'}, 1fr))`,
          gap: 16,
          marginBottom: 52,
        }}>
          {companies.map((co, i) => {
            // Collect summaries for ALL products (for multi-product carousel)
            const productSummaries = (co.products || []).map(p => ({
              product: p,
              summary: summaries[`${co.name}:${p}`],
            })).filter(ps => ps.summary)
            return (
            <CompanyCard
              key={co.name}
              company={co}
              summary={summaries[`${co.name}:${co.products?.[0]}`]}
              productSummaries={productSummaries}
              index={i}
              onClick={() => handleOpen(co)}
              isMobile={isMobile}
            />
          )})}
          {companies.length === 0 && <EmptyState />}
        </div>

        {/* ── Resources section ── */}
        <div style={{ paddingTop: 28, borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
            <span style={{
              fontSize: 13, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.14em', color: 'var(--text-muted)',
            }}>
              Resources
            </span>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? '260px' : '320px'}, 1fr))`,
            gap: 16,
          }}>
            <OperatorCard />
            <FrameworkCard />
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtSince(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
}

// ── Card sub-components ───────────────────────────────────────────────────────
function CardDivider() {
  return <div style={{ width: 1, alignSelf: 'stretch', background: 'var(--border)', margin: '0 2px' }} />
}

function CardStat({ value, label, color }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 500,
        letterSpacing: '-0.02em', lineHeight: 1, color,
      }}>
        {value ?? '—'}
      </div>
      <div style={{
        fontSize: 8, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.1em', color: 'var(--text-faint)', marginTop: 5,
      }}>
        {label}
      </div>
    </div>
  )
}

function CardRow({ label, children, loading }) {
  return (
    <div style={{
      marginTop: 10,
      background: 'var(--bg-deep)',
      border: '1px solid var(--border)',
      borderRadius: 6,
      padding: '10px 12px',
    }}>
      <div style={{
        fontSize: 7, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.14em', color: 'var(--text-faint)', marginBottom: 8,
      }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, minHeight: 36 }}>
        {loading ? (
          <>
            {[60, 50, 50].map((w, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
                <div style={{
                  width: w, height: 28, borderRadius: 4,
                  background: 'var(--bg-surface)', border: '1px solid var(--border)',
                }} />
              </div>
            ))}
          </>
        ) : children}
      </div>
    </div>
  )
}

// ── Company card ─────────────────────────────────────────────────────────────
function CompanyCard({ company, summary, productSummaries = [], index, onClick, isMobile }) {
  const [hovered, setHovered] = useState(false)
  const [carouselIdx, setCarouselIdx] = useState(0)
  const safeName = typeof company.name === 'string' ? company.name : String(company.name ?? '')
  const initials = safeName.slice(0, 2).toUpperCase()
  const meta     = getCompanyMeta(safeName)
  const isMultiProduct = productSummaries.length > 1

  // Auto-rotate carousel for multi-product companies
  // Uses a ref to avoid re-creating interval on every render
  const productCount = productSummaries.length
  useEffect(() => {
    if (productCount <= 1 || hovered) return
    const timer = setInterval(() => setCarouselIdx(i => (i + 1) % productCount), 3500)
    return () => clearInterval(timer)
  }, [productCount, hovered])

  // Active product summary for carousel
  const activePS = isMultiProduct ? productSummaries[carouselIdx] : null
  const activeSummary = activePS?.summary || summary

  // Use custom labels from summary if provided (Tamara returns face_value_label, deals_label)
  const fvLabel   = activeSummary?.face_value_label || 'Face Value'
  const dlLabel   = activeSummary?.deals_label || 'Deals'

  const faceValue = activeSummary?.total_purchase_value != null
    ? `$${(activeSummary.total_purchase_value / 1_000_000).toFixed(0)}M`
    : null
  const deals     = activeSummary?.total_deals != null
    ? activeSummary.total_deals.toLocaleString()
    : null
  const since     = fmtSince(company.since)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.08, ease: 'easeOut' }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background:    'var(--bg-surface)',
        border:        `1px solid ${hovered ? 'rgba(201,168,76,0.45)' : 'var(--border)'}`,
        borderRadius:  'var(--radius-md)',
        padding:       isMobile ? '16px 14px 12px' : '22px 22px 18px',
        cursor:        'pointer',
        minHeight:     isMobile ? 180 : 210,
        display:       'flex',
        flexDirection: 'column',
        position:      'relative',
        overflow:      'hidden',
        boxShadow:     hovered ? 'var(--shadow-glow-gold)' : 'none',
        transition:    'border-color 0.2s, box-shadow 0.2s, transform 0.22s ease',
        transform:     hovered
          ? 'translateY(-3px) perspective(700px) rotateX(1.5deg)'
          : 'translateY(0) perspective(700px) rotateX(0deg)',
      }}
    >
      {/* Animated top border on hover */}
      <div style={{
        position: 'absolute', top: 0, left: 0, height: 2,
        background: 'linear-gradient(90deg, var(--gold), rgba(201,168,76,0.3))',
        width: hovered ? '100%' : '0%',
        transition: 'width 0.3s ease',
      }} />

      {/* Gold left accent bar */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: 'var(--gold)',
        borderRadius: '10px 0 0 10px',
        opacity: hovered ? 1 : 0.35,
        transition: 'opacity 0.2s',
      }} />

      {/* Header row: initials + name + flag */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Initials box */}
          <div style={{
            width: 38, height: 38, flexShrink: 0,
            background: 'linear-gradient(135deg, var(--gold), var(--gold-dim))',
            borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 800, color: '#000',
          }}>
            {initials}
          </div>
          <div>
            <div style={{
              fontSize: 15, fontWeight: 700, color: 'var(--text-primary)',
              letterSpacing: '-0.01em', lineHeight: 1.2,
            }}>
              {safeName.toUpperCase()}
            </div>
            {meta.assetClass && (
              <div style={{
                fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
                letterSpacing: '0.1em', color: 'var(--text-muted)', marginTop: 3,
              }}>
                {meta.assetClass}
              </div>
            )}
          </div>
        </div>

        {/* Country flag(s) + region */}
        {meta.region && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            background: 'var(--bg-deep)',
            border: '1px solid var(--border)',
            borderRadius: 20, padding: '3px 9px',
            flexShrink: 0,
          }}>
            {Array.isArray(meta.countryCode)
              ? meta.countryCode.map(cc => (
                  <img key={cc} src={`https://flagcdn.com/16x12/${cc}.png`}
                    width="16" height="12" alt={cc}
                    style={{ borderRadius: 2, display: 'block' }} />
                ))
              : meta.countryCode && (
                  <img src={`https://flagcdn.com/16x12/${meta.countryCode}.png`}
                    width="16" height="12" alt={meta.region}
                    style={{ borderRadius: 2, display: 'block' }} />
                )
            }
            <span style={{
              fontSize: 9, fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: '0.08em',
              color: 'var(--text-muted)',
            }}>
              {meta.region}
            </span>
          </div>
        )}
      </div>

      {/* Row 1 — Tape Analytics (with carousel for multi-product) */}
      <div style={{ position: 'relative', overflow: 'hidden' }}>
        {isMultiProduct && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 4, paddingRight: 4,
          }}>
            <span style={{
              fontSize: 8, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.12em', color: 'var(--gold)', opacity: 0.7,
            }}>
              {activePS?.product || ''}
            </span>
            {/* Dot indicators */}
            <div style={{ display: 'flex', gap: 4 }}>
              {productSummaries.map((_, di) => (
                <div key={di} onClick={(e) => { e.stopPropagation(); setCarouselIdx(di) }}
                  style={{
                    width: 6, height: 6, borderRadius: '50%', cursor: 'pointer',
                    background: di === carouselIdx ? 'var(--gold)' : 'var(--border)',
                    transition: 'background 0.2s',
                  }} />
              ))}
            </div>
          </div>
        )}
        <motion.div
          key={isMultiProduct ? carouselIdx : 'single'}
          initial={isMultiProduct ? { opacity: 0, x: 20 } : false}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.3 }}
        >
          <CardRow label={isMultiProduct ? null : "Tape Analytics"} loading={!activeSummary}>
            <CardStat value={faceValue} label={fvLabel} color="var(--gold)" />
            <CardDivider />
            <CardStat value={deals}     label={dlLabel} color="var(--gold)" />
            <CardDivider />
            <CardStat value={since}     label="Since"      color="var(--gold)" />
          </CardRow>
        </motion.div>
      </div>

      {/* Row 2 — Live Portfolio / Facility (context-aware) */}
      <CardRow label={isMultiProduct ? "Facility" : "Live Portfolio"}>
        {isMultiProduct ? (<>
          <CardStat value={activeSummary?.facility_limit ? `$${(activeSummary.facility_limit / 1e9).toFixed(1)}B` : '--'} label="Limit" color="var(--teal)" />
          <CardDivider />
          <CardStat value={activeSummary?.merchants ? `${(activeSummary.merchants / 1e3).toFixed(0)}K` : '--'} label="Merchants" color="var(--teal)" />
          <CardDivider />
          <CardStat value={activeSummary?.registered_users ? `${(activeSummary.registered_users / 1e6).toFixed(0)}M` : '--'} label="Users" color="var(--teal)" />
        </>) : (<>
          <CardStat value="--" label="Borr. Base"  color="var(--text-faint)" />
          <CardDivider />
          <CardStat value="--" label="PAR 30+"     color="var(--text-faint)" />
          <CardDivider />
          <CardStat value="--" label="Covenants"   color="var(--text-faint)" />
        </>)}
      </CardRow>

      {/* Footer */}
      <div style={{
        marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.03em' }}>
          Open Dashboard
        </span>
        <span style={{
          color: hovered ? 'var(--gold)' : 'var(--text-faint)',
          transition: 'color 0.15s, transform 0.15s',
          transform: hovered ? 'translateX(3px)' : 'translateX(0)',
          display: 'inline-block', fontSize: 15,
        }}>→</span>
      </div>
    </motion.div>
  )
}

// ── Operator resource card ───────────────────────────────────────────────────
function OperatorCard() {
  const [hovered, setHovered] = useState(false)
  return (
    <Link
      to="/operator"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        textDecoration: 'none', display: 'block',
        background:    'var(--bg-surface)',
        border:        `1px solid ${hovered ? 'rgba(201,168,76,0.4)' : 'var(--border)'}`,
        borderRadius:  'var(--radius-md)',
        padding:       '22px 22px 18px',
        cursor:        'pointer',
        position:      'relative', overflow: 'hidden',
        transition:    'border-color 0.2s, box-shadow 0.2s, transform 0.18s',
        boxShadow:     hovered ? 'var(--shadow-glow-gold)' : 'none',
        transform:     hovered ? 'translateY(-2px)' : 'translateY(0)',
      }}
    >
      <div style={{
        position: 'absolute', top: 0, left: 0, height: 2, right: 0,
        background: hovered ? 'linear-gradient(90deg, var(--gold), transparent)' : 'transparent',
        transition: 'background 0.2s',
      }} />
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: 'var(--gold)', borderRadius: '10px 0 0 10px',
        opacity: hovered ? 1 : 0.35, transition: 'opacity 0.2s',
      }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <div style={{
          width: 38, height: 38,
          background: 'linear-gradient(135deg, var(--gold), rgba(201,168,76,0.4))',
          borderRadius: 8,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 18, flexShrink: 0,
        }}>
          &#9881;
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            Command Center
          </div>
          <div style={{
            fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
            letterSpacing: '0.1em', color: 'var(--gold)', marginTop: 3,
          }}>
            Operator
          </div>
        </div>
      </div>

      <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.65, margin: '0 0 16px' }}>
        Platform health, data gaps, follow-ups, operations menu,
        and institutional memory — your cockpit for running the fund.
      </p>

      <div style={{
        paddingTop: 14, borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Open Command Center</span>
        <span style={{
          color: hovered ? 'var(--gold)' : 'var(--text-faint)',
          transition: 'color 0.15s, transform 0.15s',
          transform: hovered ? 'translateX(3px)' : 'translateX(0)',
          display: 'inline-block', fontSize: 15,
        }}>→</span>
      </div>
    </Link>
  )
}

// ── Framework resource card ──────────────────────────────────────────────────
function FrameworkCard() {
  const [hovered, setHovered] = useState(false)
  return (
    <Link
      to="/framework"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        textDecoration: 'none', display: 'block',
        background:    'var(--bg-surface)',
        border:        `1px solid ${hovered ? 'rgba(45,212,191,0.4)' : 'var(--border)'}`,
        borderRadius:  'var(--radius-md)',
        padding:       '22px 22px 18px',
        cursor:        'pointer',
        position:      'relative', overflow: 'hidden',
        transition:    'border-color 0.2s, box-shadow 0.2s, transform 0.18s',
        boxShadow:     hovered ? '0 0 20px rgba(45,212,191,0.08)' : 'none',
        transform:     hovered ? 'translateY(-2px)' : 'translateY(0)',
      }}
    >
      <div style={{
        position: 'absolute', top: 0, left: 0, height: 2, right: 0,
        background: hovered ? 'linear-gradient(90deg, var(--teal), transparent)' : 'transparent',
        transition: 'background 0.2s',
      }} />
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: 'var(--teal)', borderRadius: '10px 0 0 10px',
        opacity: hovered ? 1 : 0.35, transition: 'opacity 0.2s',
      }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <div style={{
          width: 38, height: 38,
          background: 'linear-gradient(135deg, var(--teal), rgba(45,212,191,0.4))',
          borderRadius: 8,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 18, flexShrink: 0,
        }}>
          📐
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            Analysis Framework
          </div>
          <div style={{
            fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
            letterSpacing: '0.1em', color: 'var(--teal)', marginTop: 3,
          }}>
            Methodology
          </div>
        </div>
      </div>

      <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.65, margin: '0 0 16px' }}>
        The 5-level analytical hierarchy, metric definitions, and philosophy
        guiding every dashboard, chart, and AI insight in Laith.
      </p>

      <div style={{
        paddingTop: 14, borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Read Framework</span>
        <span style={{
          color: hovered ? 'var(--teal)' : 'var(--text-faint)',
          transition: 'color 0.15s, transform 0.15s',
          transform: hovered ? 'translateX(3px)' : 'translateX(0)',
          display: 'inline-block', fontSize: 15,
        }}>→</span>
      </div>
    </Link>
  )
}

function EmptyState() {
  return (
    <div style={{
      gridColumn: '1 / -1', padding: '48px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
      color: 'var(--text-muted)', fontSize: 13,
    }}>
      <div style={{ fontSize: 32, opacity: 0.25 }}>◻</div>
      <div>No companies found. Check that data directories are set up correctly.</div>
    </div>
  )
}
