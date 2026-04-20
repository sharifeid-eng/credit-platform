import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getPlatformStats } from '../services/api'

// ── Palette (skill-guide) ────────────────────────────────────────────────────
const PAL = {
  frontend:  { fill: 'rgba(8, 51, 68, 0.4)',    stroke: '#22d3ee', label: 'Frontend'     },
  backend:   { fill: 'rgba(6, 78, 59, 0.4)',    stroke: '#34d399', label: 'Backend'      },
  database:  { fill: 'rgba(76, 29, 149, 0.4)',  stroke: '#a78bfa', label: 'Data Layer'   },
  aws:       { fill: 'rgba(120, 53, 15, 0.3)',  stroke: '#fbbf24', label: 'AI / Cloud'   },
  security:  { fill: 'rgba(136, 19, 55, 0.4)',  stroke: '#fb7185', label: 'Security'     },
  bus:       { fill: 'rgba(251, 146, 60, 0.3)', stroke: '#fb923c', label: 'Intelligence' },
  external:  { fill: 'rgba(30, 41, 59, 0.5)',   stroke: '#94a3b8', label: 'External'     },
}

const DIAG_FONT = "'JetBrains Mono', 'IBM Plex Mono', monospace"

// Inject the JetBrains Mono stylesheet once
function JetBrainsLoader() {
  useEffect(() => {
    const id = 'jetbrains-mono-architecture'
    if (document.getElementById(id)) return
    const link = document.createElement('link')
    link.id = id
    link.rel = 'stylesheet'
    link.href = 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap'
    document.head.appendChild(link)
  }, [])
  return null
}

// ── SVG building blocks ──────────────────────────────────────────────────────
function Box({ x, y, w, h, kind, title, sublines = [], rx = 6 }) {
  const c = PAL[kind] || PAL.external
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={rx} ry={rx}
            fill={c.fill} stroke={c.stroke} strokeWidth={1.4} />
      <text x={x + w / 2} y={y + 20} textAnchor="middle"
            fill={c.stroke} fontFamily={DIAG_FONT} fontSize={12} fontWeight={600}>
        {title}
      </text>
      {sublines.map((s, i) => (
        <text key={i} x={x + w / 2} y={y + 40 + i * 13} textAnchor="middle"
              fill="#cbd5e1" fontFamily={DIAG_FONT} fontSize={9} fontWeight={500}>
          {s}
        </text>
      ))}
    </g>
  )
}

// Platform boundary (dashed)
function Boundary({ x, y, w, h, label }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} ry={10}
            fill="none" stroke="#94a3b8" strokeWidth={1} strokeDasharray="6 5"
            opacity={0.55} />
      <text x={x + 16} y={y + 18} fill="#94a3b8"
            fontFamily={DIAG_FONT} fontSize={9} fontWeight={700}
            letterSpacing="0.14em">
        {label?.toUpperCase()}
      </text>
    </g>
  )
}

// Arrow (straight or curved) with short label
function Arrow({ from, to, label, curved = false, dy = 0, color = '#64748b' }) {
  const [x1, y1] = from
  const [x2, y2] = to
  let path
  if (curved) {
    const cx = (x1 + x2) / 2
    const cy = (y1 + y2) / 2 + dy
    path = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`
  } else {
    path = `M ${x1} ${y1} L ${x2} ${y2}`
  }
  const midX = (x1 + x2) / 2
  const midY = (y1 + y2) / 2 + (curved ? dy * 0.5 : 0)
  return (
    <g>
      <path d={path} fill="none" stroke={color} strokeWidth={1.1}
            markerEnd="url(#arrow)" />
      {label && (
        <g>
          <rect x={midX - label.length * 3.2 - 4} y={midY - 8} width={label.length * 6.4 + 8} height={14}
                fill="#121C27" opacity={0.85} rx={2} />
          <text x={midX} y={midY + 2} textAnchor="middle"
                fill="#cbd5e1" fontFamily={DIAG_FONT} fontSize={8}>
            {label}
          </text>
        </g>
      )}
    </g>
  )
}

// Legend block
function Legend({ x, y }) {
  const keys = ['frontend', 'backend', 'database', 'bus', 'security', 'aws', 'external']
  return (
    <g>
      <rect x={x} y={y} width={160} height={keys.length * 18 + 18} rx={6}
            fill="rgba(13, 21, 32, 0.8)" stroke="#243040" strokeWidth={1} />
      <text x={x + 10} y={y + 16} fill="#94a3b8"
            fontFamily={DIAG_FONT} fontSize={8} fontWeight={700}
            letterSpacing="0.12em">LEGEND</text>
      {keys.map((k, i) => (
        <g key={k}>
          <rect x={x + 12} y={y + 26 + i * 18} width={12} height={10} rx={2}
                fill={PAL[k].fill} stroke={PAL[k].stroke} strokeWidth={1} />
          <text x={x + 30} y={y + 35 + i * 18}
                fill="#cbd5e1" fontFamily={DIAG_FONT} fontSize={9}>
            {PAL[k].label}
          </text>
        </g>
      ))}
    </g>
  )
}

// Bottom summary strip (3 columns)
function SummaryStrip({ y, stats }) {
  const cols = [
    {
      label: 'Core Stack',
      items: [
        'React + Vite (dark-themed SPA)',
        'FastAPI + Pydantic (Python 3.14)',
        'Postgres 18.3 + SQLAlchemy 2.0',
        'Framer Motion + Recharts',
      ],
      accent: '#22d3ee',
    },
    {
      label: 'Data Layer',
      items: [
        `${stats?.db_tables ?? '—'} Postgres tables (ORM + Alembic)`,
        `${stats?.dataroom_docs ?? '—'} data-room documents (TF-IDF + RAG)`,
        `${stats?.legal_docs ?? '—'} legal facility PDFs (5-pass extraction)`,
        `${stats?.mind_entries ?? '—'} mind entries across all companies`,
      ],
      accent: '#a78bfa',
    },
    {
      label: 'Intelligence',
      items: [
        `${stats?.ai_tiers ?? 5} AI tiers (Opus / Sonnet / Haiku)`,
        'Knowledge graph + thesis drift detection',
        'Closed-loop learning from corrections',
        `${stats?.framework_sections ?? '—'} framework sections · ${stats?.tests ?? '—'} tests`,
      ],
      accent: '#fb923c',
    },
  ]
  return (
    <g>
      <rect x={40} y={y} width={1360} height={160} rx={8}
            fill="rgba(13, 21, 32, 0.6)" stroke="#243040" strokeWidth={1} />
      {cols.map((c, idx) => {
        const colX = 60 + idx * 450
        return (
          <g key={c.label}>
            <text x={colX} y={y + 22} fill={c.accent}
                  fontFamily={DIAG_FONT} fontSize={10} fontWeight={700}
                  letterSpacing="0.14em">
              {c.label.toUpperCase()}
            </text>
            {c.items.map((it, i) => (
              <text key={i} x={colX} y={y + 44 + i * 20}
                    fill="#cbd5e1" fontFamily={DIAG_FONT} fontSize={10}>
                · {it}
              </text>
            ))}
          </g>
        )
      })}
    </g>
  )
}

// ── The actual diagram ───────────────────────────────────────────────────────
function Diagram({ stats }) {
  const n = stats?.totals || {}
  return (
    <div style={{
      background: 'rgba(13, 21, 32, 0.5)',
      border: '1px solid var(--border)',
      borderRadius: 10, padding: 18, overflowX: 'auto',
    }}>
      <svg viewBox="0 0 1440 1060" style={{ width: '100%', height: 'auto', minWidth: 960 }}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
                  markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
          </marker>
        </defs>

        {/* Title */}
        <text x={40} y={30} fill="#e8eaf0"
              fontFamily={DIAG_FONT} fontSize={16} fontWeight={700}>
          Laith — Private Credit Platform Architecture
        </text>
        <text x={40} y={50} fill="#8494a7"
              fontFamily={DIAG_FONT} fontSize={9}>
          Live diagram · stats fetched from /platform-stats on load
        </text>

        {/* Users (left) */}
        <Box kind="external" x={40} y={140} w={160} h={70}
             title="Analyst / IC"
             sublines={['Browser (SPA)', 'Cloudflare Access']} />
        <Box kind="external" x={40} y={340} w={160} h={70}
             title="Portfolio Co."
             sublines={['Klaim · SILQ · Tamara', 'Invoice/payment push']} />

        {/* Platform boundary */}
        <Boundary x={240} y={90} w={940} h={620} label="Laith Platform (Docker · Hetzner VPS)" />

        {/* Security gateway */}
        <Box kind="security" x={260} y={130} w={160} h={70}
             title="Cloudflare JWT"
             sublines={['RS256 verification', 'Role: admin / viewer']} />
        <Box kind="security" x={260} y={340} w={160} h={70}
             title="X-API-Key"
             sublines={['SHA-256 hash', 'Org-scoped']} />

        {/* Frontend */}
        <Box kind="frontend" x={460} y={120} w={220} h={280}
             title="React + Vite SPA" sublines={[
               `${n.companies ?? '—'} company dashboards`,
               '18-tab Tape Analytics',
               '6-tab Portfolio Analytics',
               '8-tab Legal Analysis',
               'Research Hub + IC Memos',
               'Operator Command Center',
               '',
               'Framer Motion + Recharts',
             ]} />

        {/* Backend (FastAPI) — central */}
        <Box kind="backend" x={720} y={120} w={220} h={70}
             title="FastAPI"
             sublines={[`${n.routes ?? '—'} routes · Python 3.14`]} />
        <Box kind="backend" x={720} y={210} w={220} h={50}
             title="Tape & Portfolio Analytics"
             sublines={['compute_* functions (pure)']} />
        <Box kind="backend" x={720} y={275} w={220} h={50}
             title="Legal Engine (5-pass)"
             sublines={[`${n.legal_docs ?? '—'} PDFs extracted`]} />
        <Box kind="backend" x={720} y={340} w={220} h={50}
             title="Memo Engine"
             sublines={['Hybrid 6-stage pipeline']} />
        <Box kind="backend" x={720} y={405} w={220} h={50}
             title="Research Hub (RAG)"
             sublines={['Claude citations']} />
        <Box kind="backend" x={720} y={470} w={220} h={50}
             title="Integration API"
             sublines={['Invoices · Payments · Stmts']} />

        {/* Data & Intelligence (right inside boundary) */}
        <Box kind="database" x={980} y={130} w={180} h={65}
             title="PostgreSQL"
             sublines={[`${n.db_tables ?? 7} tables · Alembic`]} />
        <Box kind="database" x={980} y={210} w={180} h={65}
             title="Data Room"
             sublines={[`${n.dataroom_docs ?? '—'} docs · TF-IDF`]} />
        <Box kind="bus" x={980} y={295} w={180} h={100}
             title="Living Mind"
             sublines={[
               'Master · Company',
               'Knowledge Graph',
               'Thesis Tracker',
             ]} />
        <Box kind="bus" x={980} y={410} w={180} h={65}
             title="Intelligence Engine"
             sublines={['Cross-company patterns']} />
        <Box kind="database" x={980} y={490} w={180} h={50}
             title="AI Cache"
             sublines={['Disk + in-memory']} />

        {/* External services (right) */}
        <Box kind="aws" x={1220} y={150} w={180} h={80}
             title="Anthropic API"
             sublines={['Opus 4.7 · Sonnet 4.6', 'Haiku 4.5 · prompt cache']} />
        <Box kind="aws" x={1220} y={270} w={180} h={70}
             title="Cloudflare Access"
             sublines={['Login · JWT issuance']} />
        <Box kind="aws" x={1220} y={380} w={180} h={60}
             title="FX Rate API"
             sublines={['exchangerate-api.com']} />

        {/* Legend */}
        <Legend x={1220} y={470} />

        {/* Arrows — user journey */}
        <Arrow from={[200, 175]} to={[260, 165]}  label="HTTPS" />
        <Arrow from={[420, 165]} to={[460, 180]}  label="Cookie" />
        <Arrow from={[680, 180]} to={[720, 155]}  label="REST" />
        <Arrow from={[200, 375]} to={[260, 375]}  label="HTTPS" />
        <Arrow from={[420, 375]} to={[720, 495]}  label="Auth" curved dy={-60} />

        {/* Backend → Data */}
        <Arrow from={[940, 155]} to={[980, 162]}  label="SQL" />
        <Arrow from={[940, 235]} to={[980, 240]}  label="Read" />
        <Arrow from={[940, 300]} to={[980, 325]}  label="Compile" curved dy={-10} />
        <Arrow from={[940, 365]} to={[980, 345]}  label="Query" curved dy={15} />
        <Arrow from={[940, 430]} to={[980, 440]}  label="RAG" />
        <Arrow from={[940, 495]} to={[980, 510]}  label="Cache" />

        {/* Mind internal: Intelligence ← Mind */}
        <Arrow from={[1070, 395]} to={[1070, 410]} color="#fb923c" />

        {/* Backend → Anthropic (short hop at boundary, keeps label clear) */}
        <Arrow from={[1180, 180]} to={[1220, 190]}  label="LLM" color="#fbbf24" />

        {/* JWT verify — Cloudflare JWT (inside) to Cloudflare Access (outside).
            Route over the top so it doesn't cross the central backend stack. */}
        <Arrow from={[340, 130]} to={[1220, 295]} curved dy={-180} color="#fb7185" />

        {/* Backend → FX (short hop at boundary) */}
        <Arrow from={[1180, 235]} to={[1220, 405]}  label="FX" curved dy={30} color="#fbbf24" />

        {/* Summary strip */}
        <SummaryStrip y={870} stats={n} />
      </svg>
    </div>
  )
}

// ── Feedback Loops diagram ───────────────────────────────────────────────────
// Three loops show HOW the platform gets smarter. The component diagram above
// shows WHAT the platform is made of. This view flattens the noise and makes
// the feedback paths the story.
const LOOPS = [
  {
    id: 'ingestion',
    number: '①',
    label: 'Ingestion Loop',
    color: '#34d399',
    caption: 'Tape → Mind → Thesis drift → Briefing → Analyst',
    steps: [
      { kind: 'external', title: 'Analyst / Portfolio Co.', body: 'Uploads tape' },
      { kind: 'backend',  title: 'Ingestion',               body: 'Parser · classifier' },
      { kind: 'bus',      title: 'Mind Compiler',           body: 'Entity extraction' },
      { kind: 'bus',      title: 'Thesis Tracker',          body: 'Drift check' },
      { kind: 'backend',  title: 'Morning Briefing',        body: 'Urgency scoring' },
    ],
  },
  {
    id: 'learning',
    number: '②',
    label: 'Learning Loop',
    color: '#fbbf24',
    caption: 'Correction → Classify → Rule → AI context → future queries',
    steps: [
      { kind: 'external', title: 'Analyst',            body: 'Thumbs-down / edit' },
      { kind: 'backend',  title: 'Chat Feedback API',  body: 'POST /chat-feedback' },
      { kind: 'bus',      title: 'Learning Engine',    body: 'Auto-classify' },
      { kind: 'bus',      title: 'Rule Store',         body: 'KnowledgeNode (rule)' },
      { kind: 'bus',      title: 'AI Context Builder', body: '5-layer injection' },
    ],
  },
  {
    id: 'intelligence',
    number: '③',
    label: 'Intelligence Loop',
    color: '#a78bfa',
    caption: 'Document → Entity → Cross-co pattern → Briefing → Analyst',
    steps: [
      { kind: 'database', title: 'Data Room',               body: 'Ingested docs' },
      { kind: 'bus',      title: 'Entity Extractor',        body: '7 entity types' },
      { kind: 'bus',      title: 'Intelligence Engine',     body: 'Cross-company scan' },
      { kind: 'bus',      title: 'Master Mind',             body: 'Pattern store' },
      { kind: 'backend',  title: 'Briefing / Exec Summary', body: 'Surfaces pattern' },
    ],
  },
]

function LoopStep({ x, y, w, h, step, loopColor }) {
  const c = PAL[step.kind] || PAL.external
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={6}
            fill={c.fill} stroke={c.stroke} strokeWidth={1.2} />
      <text x={x + w / 2} y={y + 17} textAnchor="middle"
            fill={c.stroke} fontFamily={DIAG_FONT} fontSize={10} fontWeight={600}>
        {step.title}
      </text>
      <text x={x + w / 2} y={y + 32} textAnchor="middle"
            fill="#cbd5e1" fontFamily={DIAG_FONT} fontSize={8}>
        {step.body}
      </text>
    </g>
  )
}

function LoopRow({ y, loop, width = 1360 }) {
  const stepW = 180
  const stepH = 46
  const gap   = (width - 80 - 60 - (LOOPS[0].steps.length * stepW)) / (LOOPS[0].steps.length - 1)
  const leftPad = 80

  return (
    <g>
      {/* Loop header (number + label) */}
      <circle cx={40 + 18} cy={y + stepH / 2} r={18}
              fill={loop.color} opacity={0.2} stroke={loop.color} strokeWidth={1.4} />
      <text x={40 + 18} y={y + stepH / 2 + 6} textAnchor="middle"
            fill={loop.color} fontFamily={DIAG_FONT} fontSize={18} fontWeight={700}>
        {loop.number}
      </text>

      {/* Loop steps */}
      {loop.steps.map((step, i) => {
        const x = leftPad + i * (stepW + gap)
        return <LoopStep key={i} x={x} y={y} w={stepW} h={stepH} step={step} loopColor={loop.color} />
      })}

      {/* Forward arrows between steps */}
      {loop.steps.slice(0, -1).map((_, i) => {
        const x1 = leftPad + i * (stepW + gap) + stepW
        const x2 = leftPad + (i + 1) * (stepW + gap)
        const yMid = y + stepH / 2
        return (
          <path key={`a${i}`}
                d={`M ${x1} ${yMid} L ${x2 - 3} ${yMid}`}
                fill="none" stroke={loop.color} strokeWidth={1.8}
                markerEnd={`url(#arrow-${loop.id})`} />
        )
      })}

      {/* Closing arc — last step returns to first (the "loop" part) */}
      {(() => {
        const lastX = leftPad + (loop.steps.length - 1) * (stepW + gap) + stepW / 2
        const firstX = leftPad + stepW / 2
        const dipY = y + stepH + 22
        return (
          <g>
            <path d={`M ${lastX} ${y + stepH} Q ${(lastX + firstX) / 2} ${dipY + 16} ${firstX} ${y + stepH}`}
                  fill="none" stroke={loop.color} strokeWidth={1.4}
                  strokeDasharray="4 4" opacity={0.7}
                  markerEnd={`url(#arrow-${loop.id})`} />
            <text x={(lastX + firstX) / 2} y={dipY + 12} textAnchor="middle"
                  fill={loop.color} fontFamily={DIAG_FONT} fontSize={9}
                  opacity={0.85}>
              closes the loop · {loop.caption}
            </text>
          </g>
        )
      })()}
    </g>
  )
}

function LoopsDiagram() {
  const rowGap = 150   // was 120 — more breathing room between rows
  const topPad = 90    // was 60 — room for the first loop's header above its row
  const totalH = topPad + LOOPS.length * rowGap + 40

  return (
    <div style={{
      background: 'rgba(13, 21, 32, 0.5)',
      border: '1px solid var(--border)',
      borderRadius: 10, padding: 18, overflowX: 'auto',
    }}>
      <svg viewBox={`0 0 1440 ${totalH}`} style={{ width: '100%', height: 'auto', minWidth: 960 }}>
        <defs>
          {LOOPS.map(l => (
            <marker key={l.id} id={`arrow-${l.id}`} viewBox="0 0 10 10" refX="9" refY="5"
                    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={l.color} />
            </marker>
          ))}
        </defs>

        {/* Title */}
        <text x={40} y={26} fill="#e8eaf0"
              fontFamily={DIAG_FONT} fontSize={14} fontWeight={700}>
          Feedback Loops — how the platform gets smarter
        </text>
        <text x={40} y={44} fill="#8494a7"
              fontFamily={DIAG_FONT} fontSize={9}>
          Each loop closes back on itself · every analyst action influences future AI output
        </text>

        {LOOPS.map((loop, i) => (
          <g key={loop.id}>
            {/* Section header — sits 24px above the row so it reads as a
                chapter title, not crowding the first box */}
            <text x={80} y={topPad + i * rowGap - 24}
                  fill={loop.color} fontFamily={DIAG_FONT} fontSize={11} fontWeight={700}
                  letterSpacing="0.18em" opacity={0.9}>
              {loop.label.toUpperCase()}
            </text>
            <LoopRow y={topPad + i * rowGap} loop={loop} />
          </g>
        ))}
      </svg>
    </div>
  )
}

// ── Capabilities section (live) ──────────────────────────────────────────────
function StatTile({ label, value, accent }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 8, padding: '16px 18px',
      }}
    >
      <div style={{
        fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.14em', color: 'var(--text-muted)', marginBottom: 6,
      }}>{label}</div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 600,
        color: accent || 'var(--text-primary)', lineHeight: 1,
      }}>{value ?? '—'}</div>
    </motion.div>
  )
}

function CapabilityCard({ title, bullets, accent }) {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 8, padding: 18,
    }}>
      <div style={{
        fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.14em', color: accent, marginBottom: 12,
      }}>{title}</div>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {bullets.map((b, i) => (
          <li key={i} style={{
            fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6,
            padding: '4px 0', borderBottom: i < bullets.length - 1 ? '1px solid var(--border)' : 'none',
          }}>
            {b}
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function Architecture() {
  const [stats, setStats]   = useState(null)
  const [error, setError]   = useState(null)

  useEffect(() => {
    getPlatformStats()
      .then(setStats)
      .catch(e => setError(e?.message || 'Failed to load platform stats'))
  }, [])

  const t = stats?.totals || {}
  const generatedAt = stats?.generated_at
    ? new Date(stats.generated_at).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
    : null

  return (
    <div style={{ minHeight: 'calc(100vh - var(--navbar-height))' }}>
      <JetBrainsLoader />
      <div style={{ maxWidth: 1480, margin: '0 auto', padding: '28px 24px 60px' }}>

        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.18em', color: '#a78bfa', marginBottom: 8,
          }}>
            Platform / Architecture
          </div>
          <h1 style={{
            margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800,
            fontSize: 34, color: 'var(--text-primary)', letterSpacing: '-0.02em',
          }}>
            Laith Platform Capabilities
          </h1>
          <p style={{
            margin: '8px 0 0', fontSize: 14, color: 'var(--text-muted)',
            maxWidth: 780, lineHeight: 1.55,
          }}>
            Live technical overview — refreshes every time you open this page.
            Stats, counts, and the diagram legend pull directly from the running
            backend, so the picture always matches what's actually deployed.
          </p>
          {generatedAt && (
            <div style={{
              fontSize: 10, color: 'var(--text-faint)', marginTop: 8,
              fontFamily: 'var(--font-mono)',
            }}>
              Snapshot: {generatedAt}
            </div>
          )}
          <div style={{ marginTop: 12 }}>
            <Link to="/" style={{
              fontSize: 11, color: 'var(--text-muted)', textDecoration: 'none',
              fontFamily: 'var(--font-mono)',
            }}>← Back to dashboard</Link>
          </div>
        </div>

        {error && (
          <div style={{
            padding: 14, background: 'rgba(240,96,96,0.12)',
            border: '1px solid rgba(240,96,96,0.3)', borderRadius: 8,
            color: '#F06060', fontSize: 13, marginBottom: 20,
          }}>
            {error}
          </div>
        )}

        {/* Live stats tiles */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
          gap: 12, marginBottom: 32,
        }}>
          <StatTile label="Companies"   value={t.companies}          accent="#22d3ee" />
          <StatTile label="Products"    value={t.products}           />
          <StatTile label="Snapshots"   value={t.snapshots}          />
          <StatTile label="Endpoints"   value={t.routes}             accent="#34d399" />
          <StatTile label="DB Tables"   value={t.db_tables}          accent="#a78bfa" />
          <StatTile label="Mind"        value={t.mind_entries}       accent="#fb923c" />
          <StatTile label="Framework"   value={t.framework_sections} accent="#34d399" />
          <StatTile label="Methodology" value={t.methodology_pages}  />
          <StatTile label="Dataroom"    value={t.dataroom_docs}      accent="#a78bfa" />
          <StatTile label="Legal Docs"  value={t.legal_docs}         accent="#fb7185" />
          <StatTile label="Tests"       value={t.tests}              />
          <StatTile label="Memos"       value={t.memos}              />
        </div>

        {/* Feedback loops diagram — HOW the platform thinks */}
        <div style={{ marginBottom: 28 }}>
          <SectionHeader text="Feedback Loops" />
          <p style={{
            margin: '-6px 0 14px', fontSize: 12, color: 'var(--text-muted)',
            maxWidth: 780, lineHeight: 1.55,
          }}>
            Three loops animate the platform. Ingestion turns new tapes into
            alerts. Learning turns analyst corrections into rules. Intelligence
            turns documents into cross-company patterns. Each closes back to
            the analyst — future AI output sees what came before.
          </p>
          <LoopsDiagram />
        </div>

        {/* Architecture diagram — WHAT the platform is made of */}
        <div style={{ marginBottom: 28 }}>
          <SectionHeader text="System Architecture" />
          <Diagram stats={stats} />
        </div>

        {/* Capability cards */}
        <div style={{ marginBottom: 20 }}>
          <SectionHeader text="What The Platform Does" />
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 14,
          }}>
            <CapabilityCard title="Self-Improvement Loops" accent="#34d399" bullets={[
              'Ingestion: every tape → mind compile → drift check',
              'Learning: every correction → auto-classified rule',
              'Intelligence: every doc → cross-company scan',
              'Rules codify into the Framework via /emerge',
              'No manual regeneration — loops close on their own',
            ]} />
            <CapabilityCard title="Tape Analytics" accent="#22d3ee" bullets={[
              '18-tab dashboards per company',
              '5-level analytical hierarchy (L1–L5)',
              'PAR, DTFC, DSO, HHI, CDR/CCR',
              'Cohort loss waterfall + vintage curves',
              'AI commentary + per-tab insights',
            ]} />
            <CapabilityCard title="Portfolio Analytics" accent="#34d399" bullets={[
              'Live borrowing base waterfall',
              'Concentration limits with breach drill-down',
              'Covenant compliance + projected breach',
              'DB-backed, tape-fallback capable',
              'Compliance certificate PDF export',
            ]} />
            <CapabilityCard title="Legal Analysis" accent="#fb7185" bullets={[
              '5-pass Claude extraction from facility PDFs',
              'Facility terms, eligibility, covenants, EOD',
              'Doc vs live-portfolio compliance comparison',
              '3-tier facility-params priority',
              'Consecutive-breach EOD tracking',
            ]} />
            <CapabilityCard title="Research Hub & Memos" accent="#a78bfa" bullets={[
              'Data-room ingestion (PDF, Excel, JSON, DOCX)',
              'Claude RAG with source citations',
              'Hybrid 6-stage memo pipeline',
              'Research packs + citation audit',
              'Dark-themed PDF export',
            ]} />
            <CapabilityCard title="Living Mind" accent="#fb923c" bullets={[
              'Master Mind (fund-level lessons)',
              'Company Mind (per-company corrections)',
              'Knowledge graph + entity extraction',
              'Thesis tracker with drift detection',
              'Closed-loop learning from corrections',
            ]} />
            <CapabilityCard title="Integration API" accent="#34d399" bullets={[
              'X-API-Key auth (org-scoped)',
              'Invoices, payments, bank statements',
              'Bulk endpoints (up to 5,000/request)',
              'Self-service onboarding flow',
              'DB-optional (tape-only fallback)',
            ]} />
          </div>
        </div>
      </div>
    </div>
  )
}

function SectionHeader({ text }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
      <span style={{
        fontSize: 12, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.14em', color: 'var(--text-muted)',
      }}>
        {text}
      </span>
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  )
}
