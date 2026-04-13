import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import useBreakpoint from '../hooks/useBreakpoint'
import {
  getOperatorStatus, getOperatorTodos, createOperatorTodo,
  updateOperatorTodo, deleteOperatorTodo, getOperatorMind,
  updateOperatorMindEntry, getOperatorBriefing, getOperatorLearning,
} from '../services/api'

// ── Section label (reused pattern from Home.jsx) ─────────────────────────────
function SectionLabel({ text, accent }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
      <span style={{
        fontSize: 13, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.14em', color: accent || 'var(--text-muted)',
      }}>
        {text}
      </span>
      <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
    </div>
  )
}

// ── Severity badge ───────────────────────────────────────────────────────────
function SeverityBadge({ severity }) {
  const colors = {
    critical: { bg: 'rgba(240,96,96,0.15)', text: '#F06060', border: 'rgba(240,96,96,0.3)' },
    warning: { bg: 'rgba(201,168,76,0.15)', text: 'var(--gold)', border: 'rgba(201,168,76,0.3)' },
    info: { bg: 'rgba(91,141,239,0.12)', text: 'var(--blue)', border: 'rgba(91,141,239,0.25)' },
  }
  const c = colors[severity] || colors.info
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
      letterSpacing: '0.08em', padding: '2px 7px', borderRadius: 4,
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
    }}>
      {severity}
    </span>
  )
}

// ── Freshness badge ──────────────────────────────────────────────────────────
function FreshnessBadge({ status, daysStale }) {
  const styles = {
    fresh: { bg: 'rgba(45,212,191,0.15)', text: 'var(--teal)', label: `${daysStale ?? 0}d` },
    stale: { bg: 'rgba(201,168,76,0.15)', text: 'var(--gold)', label: `${daysStale}d` },
    outdated: { bg: 'rgba(240,96,96,0.15)', text: '#F06060', label: `${daysStale}d` },
    unknown: { bg: 'rgba(132,148,167,0.15)', text: 'var(--text-muted)', label: '—' },
  }
  const s = styles[status] || styles.unknown
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
      padding: '2px 8px', borderRadius: 4,
      background: s.bg, color: s.text,
    }}>
      {s.label}
    </span>
  )
}

// ── Category badge ───────────────────────────────────────────────────────────
function CategoryBadge({ category }) {
  const colors = {
    framework: 'var(--teal)',
    session: 'var(--gold)',
    deep_work: 'var(--blue)',
  }
  return (
    <span style={{
      fontSize: 8, fontWeight: 700, textTransform: 'uppercase',
      letterSpacing: '0.1em', padding: '2px 6px', borderRadius: 3,
      background: 'var(--bg-deep)', color: colors[category] || 'var(--text-muted)',
      border: '1px solid var(--border)',
    }}>
      {category?.replace('_', ' ')}
    </span>
  )
}

// ── Priority badge ───────────────────────────────────────────────────────────
function PriorityBadge({ priority }) {
  const colors = { P0: '#F06060', P1: 'var(--gold)', P2: 'var(--text-muted)' }
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, fontFamily: 'var(--font-mono)',
      color: colors[priority] || 'var(--text-muted)',
    }}>
      {priority}
    </span>
  )
}

// ── Command card ─────────────────────────────────────────────────────────────
function CommandCard({ cmd }) {
  const [hovered, setHovered] = useState(false)
  const accentColors = {
    framework: 'var(--teal)',
    session: 'var(--gold)',
    deep_work: 'var(--blue)',
  }
  const accent = accentColors[cmd.category] || 'var(--text-muted)'

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? accent + '55' : 'var(--border)'}`,
        borderRadius: 8,
        padding: '12px 14px',
        transition: 'border-color 0.2s, box-shadow 0.15s',
        boxShadow: hovered ? `0 0 12px ${accent}15` : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{
          fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)',
          color: accent, letterSpacing: '-0.01em',
        }}>
          {cmd.name}
        </span>
        <CategoryBadge category={cmd.category} />
      </div>
      <p style={{
        fontSize: 11, color: 'var(--text-muted)', margin: 0,
        lineHeight: 1.5, letterSpacing: '0.01em',
      }}>
        {cmd.description}
      </p>
    </div>
  )
}

// ── Company health card ──────────────────────────────────────────────────────
function CompanyHealthCard({ health, index, onClick }) {
  const [hovered, setHovered] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? 'rgba(201,168,76,0.4)' : 'var(--border)'}`,
        borderRadius: 10,
        padding: '18px 20px',
        cursor: 'pointer',
        position: 'relative',
        overflow: 'hidden',
        transition: 'border-color 0.2s, box-shadow 0.2s, transform 0.18s',
        boxShadow: hovered ? 'var(--shadow-glow-gold)' : 'none',
        transform: hovered ? 'translateY(-2px)' : 'none',
      }}
    >
      {/* Gold left accent */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: 'var(--gold)', borderRadius: '10px 0 0 10px',
        opacity: hovered ? 1 : 0.3, transition: 'opacity 0.2s',
      }} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            {health.company.toUpperCase()}
          </div>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginTop: 2 }}>
            {health.product} · {health.currency}
          </div>
        </div>
        <FreshnessBadge status={health.tape_freshness.status} daysStale={health.tape_freshness.days_stale} />
      </div>

      {/* Stats row */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
        background: 'var(--bg-deep)', borderRadius: 6, padding: '10px 8px',
        marginBottom: health.gaps.length > 0 ? 12 : 0,
      }}>
        {[
          { label: 'Tapes', value: health.tape_count, color: 'var(--gold)' },
          { label: 'Legal', value: health.legal_extracted ? 'Yes' : '—', color: health.legal_extracted ? 'var(--teal)' : 'var(--text-faint)' },
          { label: 'Docs', value: health.dataroom_docs || '—', color: health.dataroom_docs ? 'var(--blue)' : 'var(--text-faint)' },
          { label: 'Mind', value: health.mind_total || '—', color: health.mind_total ? 'var(--teal)' : 'var(--text-faint)' },
        ].map(s => (
          <div key={s.label} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 14, fontWeight: 600, fontFamily: 'var(--font-mono)', color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 7, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-faint)', marginTop: 3 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Gaps */}
      {health.gaps.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {health.gaps.map((gap, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <SeverityBadge severity={gap.severity} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>{gap.text}</span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )
}

// ── Activity timeline item ───────────────────────────────────────────────────
function ActivityItem({ event }) {
  const actionLabels = {
    tape_loaded: 'Tape Loaded',
    ai_commentary: 'AI Commentary',
    ai_executive_summary: 'Executive Summary',
    ai_tab_insight: 'Tab Insight',
    ai_chat: 'AI Chat',
    legal_upload: 'Legal Upload',
    legal_extraction: 'Legal Extraction',
    dataroom_ingest: 'Data Room Ingest',
    memo_generated: 'Memo Generated',
    report_generated: 'Report Generated',
    research_query: 'Research Query',
    mind_entry_recorded: 'Mind Entry',
    compliance_cert: 'Compliance Cert',
    breach_notification: 'Breach Alert',
    operator_todo: 'Follow-up',
  }
  const ts = event.timestamp ? new Date(event.timestamp) : null
  const timeStr = ts ? ts.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 12, padding: '8px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      <span style={{
        fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)',
        whiteSpace: 'nowrap', marginTop: 2, minWidth: 100,
      }}>
        {timeStr}
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)' }}>
            {actionLabels[event.action] || event.action}
          </span>
          {event.company && (
            <span style={{
              fontSize: 9, fontWeight: 600, padding: '1px 6px', borderRadius: 3,
              background: 'var(--bg-deep)', color: 'var(--gold)', border: '1px solid var(--border)',
            }}>
              {event.company}
            </span>
          )}
        </div>
        {event.detail && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.4 }}>
            {event.detail}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Todo item row ────────────────────────────────────────────────────────────
function TodoItem({ item, onToggle, onDelete }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
      borderBottom: '1px solid var(--border)',
      opacity: item.completed ? 0.5 : 1,
    }}>
      <button
        onClick={() => onToggle(item.id, !item.completed)}
        style={{
          width: 18, height: 18, borderRadius: 4, flexShrink: 0,
          border: `1.5px solid ${item.completed ? 'var(--teal)' : 'var(--border)'}`,
          background: item.completed ? 'rgba(45,212,191,0.15)' : 'transparent',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--teal)', fontSize: 11,
        }}
      >
        {item.completed && '✓'}
      </button>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <PriorityBadge priority={item.priority} />
          <span style={{
            fontSize: 12, color: 'var(--text-primary)',
            textDecoration: item.completed ? 'line-through' : 'none',
          }}>
            {item.text}
          </span>
        </div>
        {item.company && (
          <span style={{
            fontSize: 9, color: 'var(--gold)', fontWeight: 600,
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            {item.company}
          </span>
        )}
      </div>
      <button
        onClick={() => onDelete(item.id)}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-faint)', fontSize: 14, padding: 4,
        }}
      >
        ×
      </button>
    </div>
  )
}

// ── Mind entry row ───────────────────────────────────────────────────────────
function MindEntryRow({ entry, onPromote }) {
  const ts = entry.timestamp ? new Date(entry.timestamp) : null
  const dateStr = ts ? ts.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'
  const source = entry._source === 'master' ? 'Master' : `${entry._company}/${entry._product}`

  return (
    <div style={{
      padding: '10px 0', borderBottom: '1px solid var(--border)',
      opacity: entry.archived ? 0.4 : 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{
          fontSize: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em',
          padding: '1px 6px', borderRadius: 3, border: '1px solid var(--border)',
          color: entry._source === 'master' ? 'var(--gold)' : 'var(--teal)',
          background: entry._source === 'master' ? 'rgba(201,168,76,0.1)' : 'rgba(45,212,191,0.1)',
        }}>
          {source}
        </span>
        <span style={{
          fontSize: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em',
          color: 'var(--text-faint)',
        }}>
          {entry.category || entry._file}
        </span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)' }}>
          {dateStr}
        </span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, paddingRight: 8 }}>
        {entry.content}
      </div>
      {entry._source === 'company' && !entry.promoted && (
        <button
          onClick={() => onPromote(entry.id)}
          style={{
            marginTop: 6, fontSize: 9, fontWeight: 700,
            background: 'none', border: '1px solid var(--border)',
            borderRadius: 4, padding: '3px 8px', cursor: 'pointer',
            color: 'var(--gold)', letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}
        >
          Promote to Master
        </button>
      )}
      {entry.promoted && (
        <span style={{
          display: 'inline-block', marginTop: 6, fontSize: 9, fontWeight: 700,
          color: 'var(--teal)', letterSpacing: '0.06em', textTransform: 'uppercase',
        }}>
          Promoted
        </span>
      )}
    </div>
  )
}

// ── Add Todo Form ────────────────────────────────────────────────────────────
function AddTodoForm({ onAdd, companies }) {
  const [text, setText] = useState('')
  const [company, setCompany] = useState('')
  const [priority, setPriority] = useState('P1')
  const [category, setCategory] = useState('general')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!text.trim()) return
    onAdd({ text: text.trim(), company: company || null, priority, category })
    setText('')
  }

  const selectStyle = {
    background: 'var(--bg-deep)', border: '1px solid var(--border)',
    borderRadius: 4, padding: '5px 8px', fontSize: 11,
    color: 'var(--text-primary)', fontFamily: 'var(--font-mono)',
  }

  return (
    <form onSubmit={handleSubmit} style={{
      display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
      padding: '10px 0', borderBottom: '1px solid var(--border)',
    }}>
      <input
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Add follow-up..."
        style={{
          flex: 1, minWidth: 180,
          background: 'var(--bg-deep)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '7px 12px', fontSize: 12,
          color: 'var(--text-primary)', fontFamily: 'var(--font-ui)',
          outline: 'none',
        }}
      />
      <select value={priority} onChange={e => setPriority(e.target.value)} style={selectStyle}>
        <option value="P0">P0</option>
        <option value="P1">P1</option>
        <option value="P2">P2</option>
      </select>
      <select value={category} onChange={e => setCategory(e.target.value)} style={selectStyle}>
        <option value="general">General</option>
        <option value="data_request">Data Request</option>
        <option value="ic_followup">IC Follow-up</option>
        <option value="bug">Bug</option>
        <option value="feature">Feature</option>
      </select>
      <select value={company} onChange={e => setCompany(e.target.value)} style={selectStyle}>
        <option value="">All</option>
        {companies.map(c => <option key={c} value={c}>{c}</option>)}
      </select>
      <button type="submit" style={{
        background: 'var(--gold)', color: '#000', border: 'none',
        borderRadius: 6, padding: '7px 16px', fontSize: 11, fontWeight: 700,
        cursor: 'pointer', letterSpacing: '0.02em',
      }}>
        Add
      </button>
    </form>
  )
}

// ── Tab button ───────────────────────────────────────────────────────────────
function TabButton({ label, active, onClick, count }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? 'rgba(201,168,76,0.12)' : 'transparent',
        border: `1px solid ${active ? 'rgba(201,168,76,0.35)' : 'var(--border)'}`,
        borderRadius: 6, padding: '6px 14px', cursor: 'pointer',
        color: active ? 'var(--gold)' : 'var(--text-muted)',
        fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-ui)',
        transition: 'all 0.15s',
        display: 'flex', alignItems: 'center', gap: 6,
      }}
    >
      {label}
      {count != null && (
        <span style={{
          fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700,
          background: active ? 'rgba(201,168,76,0.2)' : 'var(--bg-deep)',
          padding: '1px 5px', borderRadius: 3,
        }}>
          {count}
        </span>
      )}
    </button>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function OperatorCenter() {
  const [status, setStatus] = useState(null)
  const [todos, setTodos] = useState([])
  const [mindEntries, setMindEntries] = useState([])
  const [mindFilter, setMindFilter] = useState(null)
  const [briefing, setBriefing] = useState(null)
  const [learning, setLearning] = useState(null)
  const [activeTab, setActiveTab] = useState('health')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const { isMobile } = useBreakpoint()

  useEffect(() => {
    loadStatus()
  }, [])

  const loadStatus = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getOperatorStatus()
      setStatus(data)
      setTodos(data.todos || [])
    } catch (e) {
      console.error('Failed to load operator status:', e)
      setError('Failed to load operator status. Make sure the backend is running.')
    }
    setLoading(false)
  }

  const loadMind = async (company = null) => {
    try {
      const data = await getOperatorMind(company)
      setMindEntries(data.entries || [])
    } catch (e) {
      console.error('Failed to load mind entries:', e)
    }
  }

  // Load tab-specific data
  useEffect(() => {
    if (activeTab === 'mind') loadMind(mindFilter)
    if (activeTab === 'briefing' && !briefing) {
      getOperatorBriefing().then(setBriefing).catch(e => console.error('Briefing load failed:', e))
    }
    if (activeTab === 'learning' && !learning) {
      getOperatorLearning().then(setLearning).catch(e => console.error('Learning load failed:', e))
    }
  }, [activeTab, mindFilter])

  const handleAddTodo = async (item) => {
    try {
      const created = await createOperatorTodo(item)
      setTodos(prev => [...prev, created])
    } catch (e) {
      console.error('Failed to create todo:', e)
    }
  }

  const handleToggleTodo = async (id, completed) => {
    try {
      const updated = await updateOperatorTodo(id, { completed })
      setTodos(prev => prev.map(t => t.id === id ? updated : t))
    } catch (e) {
      console.error('Failed to toggle todo:', e)
    }
  }

  const handleDeleteTodo = async (id) => {
    try {
      await deleteOperatorTodo(id)
      setTodos(prev => prev.filter(t => t.id !== id))
    } catch (e) {
      console.error('Failed to delete todo:', e)
    }
  }

  const handlePromoteMind = async (entryId) => {
    try {
      await updateOperatorMindEntry(entryId, { promoted: true })
      loadMind(mindFilter)
    } catch (e) {
      console.error('Failed to promote mind entry:', e)
    }
  }

  const companies = status?.companies || []
  const companyNames = [...new Set(companies.map(c => c.company))]
  const activity = status?.activity_log || []
  const openTodos = todos.filter(t => !t.completed)
  const totalGaps = companies.reduce((acc, c) => acc + c.gaps.length, 0)

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'var(--gold)', fontSize: 14, fontFamily: 'var(--font-mono)' }}>Loading operator status...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16 }}>
        <div style={{ color: '#F06060', fontSize: 14, fontFamily: 'var(--font-mono)' }}>{error}</div>
        <button
          onClick={loadStatus}
          style={{
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 6, padding: '8px 16px', cursor: 'pointer',
            color: 'var(--text-muted)', fontSize: 12, fontWeight: 600,
            fontFamily: 'var(--font-mono)',
          }}
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', position: 'relative' }}>
      {/* Geometric background (same as Home) */}
      <div aria-hidden="true" style={{
        position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none',
        backgroundImage: 'url(/geometric-pattern.svg)',
        backgroundRepeat: 'repeat', backgroundSize: '140px 140px', opacity: 0.08,
      }} />

      <div style={{ position: 'relative', zIndex: 1, padding: isMobile ? '24px 14px 40px' : '44px 28px 60px', maxWidth: 1280, margin: '0 auto' }}>

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          style={{ marginBottom: 36 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
            <h1 style={{
              fontFamily: 'var(--font-display)', fontSize: isMobile ? 28 : 36,
              fontWeight: 800, letterSpacing: '-0.02em', margin: 0,
              background: 'linear-gradient(135deg, #E8C96A 0%, var(--gold) 40%, #A07830 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            }}>
              Command Center
            </h1>
            <button
              onClick={loadStatus}
              style={{
                background: 'var(--bg-surface)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '6px 12px', cursor: 'pointer',
                color: 'var(--text-muted)', fontSize: 11, fontWeight: 600,
                fontFamily: 'var(--font-mono)',
              }}
            >
              Refresh
            </button>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, fontFamily: 'var(--font-ui)' }}>
            Platform health, operations menu, follow-ups, and institutional memory
          </p>
        </motion.div>

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
          <TabButton label="Health" active={activeTab === 'health'} onClick={() => setActiveTab('health')} count={totalGaps > 0 ? totalGaps : null} />
          <TabButton label="Commands" active={activeTab === 'commands'} onClick={() => setActiveTab('commands')} count={status?.commands?.length} />
          <TabButton label="Follow-ups" active={activeTab === 'todos'} onClick={() => setActiveTab('todos')} count={openTodos.length || null} />
          <TabButton label="Activity" active={activeTab === 'activity'} onClick={() => setActiveTab('activity')} count={activity.length || null} />
          <TabButton label="Mind" active={activeTab === 'mind'} onClick={() => setActiveTab('mind')} />
          <TabButton label="Briefing" active={activeTab === 'briefing'} onClick={() => setActiveTab('briefing')} />
          <TabButton label="Learning" active={activeTab === 'learning'} onClick={() => setActiveTab('learning')} count={learning?.total_rules || null} />
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
          >

            {/* ── Health Tab ── */}
            {activeTab === 'health' && (
              <div>
                <SectionLabel text="Company Health Matrix" />
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? '280px' : '360px'}, 1fr))`,
                  gap: 16,
                }}>
                  {companies.map((h, i) => (
                    <CompanyHealthCard
                      key={`${h.company}-${h.product}`}
                      health={h}
                      index={i}
                      onClick={() => navigate(`/company/${h.company}/${h.product}/tape/overview`)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* ── Commands Tab ── */}
            {activeTab === 'commands' && (
              <div>
                {['framework', 'intelligence', 'session', 'deep_work'].map(cat => {
                  const cmds = (status?.commands || []).filter(c => c.category === cat)
                  if (!cmds.length) return null
                  const labels = { framework: 'Framework Commands', intelligence: 'Intelligence Commands', session: 'Session Commands', deep_work: 'Deep Work Modes' }
                  const accents = { framework: 'var(--teal)', intelligence: '#A78BFA', session: 'var(--gold)', deep_work: 'var(--blue)' }
                  return (
                    <div key={cat} style={{ marginBottom: 28 }}>
                      <SectionLabel text={labels[cat]} accent={accents[cat]} />
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? '260px' : '300px'}, 1fr))`,
                        gap: 10,
                      }}>
                        {cmds.map(cmd => <CommandCard key={cmd.name} cmd={cmd} />)}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* ── Follow-ups Tab ── */}
            {activeTab === 'todos' && (
              <div style={{ maxWidth: 700 }}>
                <SectionLabel text="Follow-ups" />
                <AddTodoForm onAdd={handleAddTodo} companies={companyNames} />
                <div style={{ marginTop: 8 }}>
                  {todos.filter(t => !t.completed).map(t => (
                    <TodoItem key={t.id} item={t} onToggle={handleToggleTodo} onDelete={handleDeleteTodo} />
                  ))}
                  {todos.filter(t => t.completed).length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-faint)', marginBottom: 8 }}>
                        Completed
                      </div>
                      {todos.filter(t => t.completed).map(t => (
                        <TodoItem key={t.id} item={t} onToggle={handleToggleTodo} onDelete={handleDeleteTodo} />
                      ))}
                    </div>
                  )}
                  {todos.length === 0 && (
                    <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                      No follow-up items. Add one above.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Activity Tab ── */}
            {activeTab === 'activity' && (
              <div style={{ maxWidth: 700 }}>
                <SectionLabel text="Activity Log" />
                {activity.length > 0 ? (
                  activity.map((e, i) => <ActivityItem key={i} event={e} />)
                ) : (
                  <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                    No activity recorded yet. Actions will appear here as you use the platform.
                  </div>
                )}
              </div>
            )}

            {/* ── Mind Tab ── */}
            {activeTab === 'mind' && (
              <div style={{ maxWidth: 700 }}>
                <SectionLabel text="Institutional Memory" />
                {/* Filter bar */}
                <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
                  <TabButton label="All" active={!mindFilter} onClick={() => setMindFilter(null)} />
                  <TabButton label="Master" active={mindFilter === '_master'} onClick={() => setMindFilter('_master')} />
                  {companyNames.map(c => (
                    <TabButton key={c} label={c} active={mindFilter === c} onClick={() => setMindFilter(c)} />
                  ))}
                </div>
                {mindEntries.length > 0 ? (
                  mindEntries.map((e, i) => (
                    <MindEntryRow key={e.id || i} entry={e} onPromote={handlePromoteMind} />
                  ))
                ) : (
                  <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                    No mind entries found. Knowledge accumulates as you use AI features.
                  </div>
                )}
              </div>
            )}

            {/* ── Briefing Tab ── */}
            {activeTab === 'briefing' && (
              <div style={{ maxWidth: 800 }}>
                <SectionLabel text="Morning Briefing" accent="#A78BFA" />
                {!briefing ? (
                  <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                    Loading briefing...
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    {/* Priority Actions */}
                    {(briefing.priority_actions || []).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>
                          Priority Actions
                        </div>
                        {briefing.priority_actions.map((item, i) => (
                          <div key={i} style={{
                            display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 14px',
                            background: 'var(--bg-surface)', border: '1px solid var(--border)',
                            borderRadius: 8, marginBottom: 8,
                          }}>
                            <SeverityBadge severity={item.severity} />
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                                {item.title}
                                {item.company && <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 8 }}>{item.company}</span>}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.description}</div>
                              {item.action && <div style={{ fontSize: 10, color: 'var(--gold)', marginTop: 4 }}>{item.action}</div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Since Last Session */}
                    {(briefing.since_last_session || []).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>
                          Since Last Session
                        </div>
                        {briefing.since_last_session.map((item, i) => (
                          <div key={i} style={{
                            padding: '8px 14px', background: 'var(--bg-surface)',
                            border: '1px solid var(--border)', borderRadius: 8, marginBottom: 6,
                          }}>
                            <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{item.title}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{item.description}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Thesis Alerts */}
                    {(briefing.thesis_alerts || []).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#F06060', marginBottom: 10 }}>
                          Thesis Alerts
                        </div>
                        {briefing.thesis_alerts.map((alert, i) => (
                          <div key={i} style={{
                            padding: '10px 14px', background: 'rgba(240,96,96,0.08)',
                            border: '1px solid rgba(240,96,96,0.2)', borderRadius: 8, marginBottom: 8,
                          }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: '#F06060' }}>{alert.company || 'Unknown'}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{alert.claim || alert.description || ''}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Recommendations */}
                    {(briefing.recommendations || []).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--teal)', marginBottom: 10 }}>
                          Recommendations
                        </div>
                        {briefing.recommendations.map((rec, i) => (
                          <div key={i} style={{
                            padding: '8px 14px', fontSize: 12, color: 'var(--text-primary)',
                            background: 'rgba(45,212,191,0.06)', border: '1px solid rgba(45,212,191,0.15)',
                            borderRadius: 8, marginBottom: 6,
                          }}>
                            {rec}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Learning Summary */}
                    {briefing.learning_summary && (
                      <div style={{
                        padding: '12px 16px', background: 'var(--bg-surface)',
                        border: '1px solid var(--border)', borderRadius: 8,
                      }}>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>
                          Learning Summary
                        </div>
                        <div style={{ display: 'flex', gap: 24 }}>
                          <div>
                            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                              {briefing.learning_summary.total_rules ?? 0}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Total Rules</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--gold)' }}>
                              {briefing.learning_summary.new_since_last_session ?? 0}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>New Since Last</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Empty state */}
                    {!(briefing.priority_actions?.length || briefing.since_last_session?.length || briefing.thesis_alerts?.length) && (
                      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                        No briefing items. Start using Intelligence System features to populate the briefing.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── Learning Tab ── */}
            {activeTab === 'learning' && (
              <div style={{ maxWidth: 800 }}>
                <SectionLabel text="Learning Engine" accent="#A78BFA" />
                {!learning ? (
                  <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                    Loading learning data...
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    {/* Stats bar */}
                    <div style={{ display: 'flex', gap: 20 }}>
                      {[
                        { label: 'Corrections', value: learning.total_corrections ?? 0, color: 'var(--text-primary)' },
                        { label: 'Rules Generated', value: learning.total_rules ?? 0, color: 'var(--gold)' },
                        { label: 'Patterns', value: (learning.patterns || []).length, color: 'var(--teal)' },
                      ].map(s => (
                        <div key={s.label} style={{
                          padding: '12px 16px', background: 'var(--bg-surface)',
                          border: '1px solid var(--border)', borderRadius: 8, flex: 1,
                        }}>
                          <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)', color: s.color }}>{s.value}</div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.label}</div>
                        </div>
                      ))}
                    </div>

                    {/* Correction Frequency */}
                    {learning.frequency?.by_type && Object.keys(learning.frequency.by_type).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>
                          Correction Types
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          {Object.entries(learning.frequency.by_type).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
                            <div key={type} style={{
                              padding: '6px 12px', background: 'var(--bg-surface)',
                              border: '1px solid var(--border)', borderRadius: 6,
                              fontSize: 11, fontFamily: 'var(--font-mono)',
                            }}>
                              <span style={{ color: 'var(--text-primary)' }}>{type}</span>
                              <span style={{ color: 'var(--gold)', marginLeft: 8 }}>{count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Auto-Generated Rules */}
                    {(learning.rules || []).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--gold)', marginBottom: 10 }}>
                          Auto-Generated Rules ({learning.rules.length})
                        </div>
                        {learning.rules.slice(0, 20).map((rule, i) => (
                          <div key={rule.id || i} style={{
                            padding: '10px 14px', background: 'var(--bg-surface)',
                            border: '1px solid var(--border)', borderRadius: 8, marginBottom: 8,
                          }}>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                              <span style={{
                                fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                                letterSpacing: '0.08em', padding: '2px 7px', borderRadius: 4,
                                background: 'rgba(167,139,250,0.15)', color: '#A78BFA',
                                border: '1px solid rgba(167,139,250,0.3)',
                              }}>
                                rule
                              </span>
                              {rule._company && (
                                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{rule._company}</span>
                              )}
                              <span style={{ fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                                {rule.timestamp?.slice(0, 10) || ''}
                              </span>
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>
                              {rule.content?.slice(0, 200) || ''}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Codification Candidates */}
                    {(learning.frequency?.codification_candidates || []).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--teal)', marginBottom: 10 }}>
                          Codification Candidates
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
                          These correction types appear 3+ times — consider promoting to methodology.
                        </div>
                        {learning.frequency.codification_candidates.map((c, i) => (
                          <div key={i} style={{
                            padding: '8px 14px', background: 'rgba(45,212,191,0.06)',
                            border: '1px solid rgba(45,212,191,0.15)', borderRadius: 8, marginBottom: 6,
                            fontSize: 12, color: 'var(--teal)', fontFamily: 'var(--font-mono)',
                          }}>
                            {c}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Recent Corrections */}
                    {(learning.corrections || []).length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10 }}>
                          Recent Corrections ({learning.corrections.length})
                        </div>
                        {learning.corrections.slice(0, 15).map((corr, i) => (
                          <div key={corr.id || i} style={{
                            padding: '8px 14px', background: 'var(--bg-surface)',
                            border: '1px solid var(--border)', borderRadius: 8, marginBottom: 6,
                          }}>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
                              <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-primary)' }}>{corr._company || ''}</span>
                              <span style={{ fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                                {corr.timestamp?.slice(0, 10) || ''}
                              </span>
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                              {corr.content?.slice(0, 150) || ''}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Empty state */}
                    {!(learning.total_corrections || learning.total_rules) && (
                      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                        No learning data yet. Corrections from memo edits and chat feedback will appear here.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
