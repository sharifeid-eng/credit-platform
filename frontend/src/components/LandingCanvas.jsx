/**
 * LandingCanvas — full-viewport canvas network animation.
 * Draws drifting "deal" nodes connected by proximity lines, with larger
 * pulsing company nodes that glow on hover.
 *
 * Props:
 *   companies      array   — list of company objects (for node count + naming)
 *   hoveredCompany string  — name of currently hovered company card (or null)
 */
import { useEffect, useRef } from 'react'

const DEAL_NODE_COUNT = 22
const PROXIMITY_THRESHOLD = 180
const FPS_CAP = 30

// Gold and teal as RGBA components
const GOLD = [201, 168, 76]
const TEAL = [45, 212, 191]

function rgba([r, g, b], a) {
  return `rgba(${r},${g},${b},${a})`
}

// Stable initial positions for company nodes (% of viewport W/H)
// Arranged in a gentle arc across the lower-centre of the viewport
const COMPANY_POSITIONS = [
  { xPct: 0.22, yPct: 0.58 },
  { xPct: 0.50, yPct: 0.48 },
  { xPct: 0.78, yPct: 0.58 },
  { xPct: 0.35, yPct: 0.72 },
  { xPct: 0.65, yPct: 0.72 },
]

function initDealNodes(W, H) {
  return Array.from({ length: DEAL_NODE_COUNT }, () => ({
    x:  Math.random() * W,
    y:  Math.random() * H,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
  }))
}

function initCompanyNodes(companies, W, H) {
  return companies.map((co, i) => {
    const pos = COMPANY_POSITIONS[i] ?? { xPct: 0.1 + i * 0.2, yPct: 0.5 }
    return {
      name:         co.name,
      x:            pos.xPct * W,
      y:            pos.yPct * H,
      pulseRingR:   0,     // expanding ring radius when hovered
      pulseRingA:   0,     // ring alpha
    }
  })
}

export default function LandingCanvas({ companies, hoveredCompany }) {
  const canvasRef         = useRef(null)
  const dealNodesRef      = useRef([])
  const companyNodesRef   = useRef([])
  const hoveredRef        = useRef(hoveredCompany)
  const rafRef            = useRef(null)
  const lastFrameRef      = useRef(0)
  const companiesCountRef = useRef(0)

  // Keep hovered ref in sync without triggering re-render/re-init
  useEffect(() => { hoveredRef.current = hoveredCompany }, [hoveredCompany])

  useEffect(() => {
    // Disable on mobile — too battery intensive
    if (window.matchMedia('(max-width: 768px)').matches) return

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    // ── Sizing ──────────────────────────────────────────────────────────────
    const setSize = () => {
      canvas.width  = window.innerWidth
      canvas.height = window.innerHeight
    }
    setSize()

    const onResize = debounce(() => {
      setSize()
      // Re-position company nodes proportionally
      companyNodesRef.current = initCompanyNodes(companies, canvas.width, canvas.height)
    }, 200)
    window.addEventListener('resize', onResize)

    // ── Init nodes ───────────────────────────────────────────────────────────
    dealNodesRef.current    = initDealNodes(canvas.width, canvas.height)
    companyNodesRef.current = initCompanyNodes(companies, canvas.width, canvas.height)
    companiesCountRef.current = companies.length

    // ── Animation loop ───────────────────────────────────────────────────────
    const animate = (timestamp) => {
      // Pause when tab hidden
      if (document.visibilityState === 'hidden') {
        rafRef.current = requestAnimationFrame(animate)
        return
      }

      // Cap to FPS_CAP
      const delta = timestamp - lastFrameRef.current
      if (delta < 1000 / FPS_CAP) {
        rafRef.current = requestAnimationFrame(animate)
        return
      }
      lastFrameRef.current = timestamp

      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      // ── Update deal node positions (Brownian drift) ──────────────────────
      dealNodesRef.current.forEach(node => {
        // Small random acceleration
        node.vx += (Math.random() - 0.5) * 0.06
        node.vy += (Math.random() - 0.5) * 0.06

        // Speed cap
        const spd = Math.sqrt(node.vx * node.vx + node.vy * node.vy)
        if (spd > 0.55) { node.vx = (node.vx / spd) * 0.55; node.vy = (node.vy / spd) * 0.55 }

        node.x += node.vx
        node.y += node.vy

        // Soft boundary bounce
        if (node.x < 10)    { node.vx = Math.abs(node.vx); node.x = 10 }
        if (node.x > W - 10) { node.vx = -Math.abs(node.vx); node.x = W - 10 }
        if (node.y < 10)    { node.vy = Math.abs(node.vy); node.y = 10 }
        if (node.y > H - 10) { node.vy = -Math.abs(node.vy); node.y = H - 10 }
      })

      // ── Draw proximity connections ───────────────────────────────────────
      const all = [...companyNodesRef.current, ...dealNodesRef.current]
      for (let i = 0; i < all.length; i++) {
        for (let j = i + 1; j < all.length; j++) {
          const a = all[i], b = all[j]
          const dx = a.x - b.x, dy = a.y - b.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist > PROXIMITY_THRESHOLD) continue

          const alpha = (1 - dist / PROXIMITY_THRESHOLD) * 0.1
          ctx.strokeStyle = rgba(GOLD, alpha)
          ctx.lineWidth   = 0.6
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.stroke()
        }
      }

      // ── Draw deal nodes ──────────────────────────────────────────────────
      dealNodesRef.current.forEach(node => {
        ctx.beginPath()
        ctx.arc(node.x, node.y, 2, 0, Math.PI * 2)
        ctx.fillStyle = rgba(TEAL, 0.22)
        ctx.fill()
      })

      // ── Draw company nodes ───────────────────────────────────────────────
      const t = timestamp * 0.0018
      companyNodesRef.current.forEach((node, i) => {
        const isHovered = hoveredRef.current === node.name
        const baseR     = isHovered ? 10 : 7
        const pulse     = Math.sin(t + i * 1.2) * 0.3 + 0.7   // 0.4 → 1.0
        const r         = baseR + pulse * 2.5

        // Glow halo
        const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, r * 3.5)
        gradient.addColorStop(0, rgba(GOLD, isHovered ? 0.32 : 0.14))
        gradient.addColorStop(1, rgba(GOLD, 0))
        ctx.beginPath()
        ctx.arc(node.x, node.y, r * 3.5, 0, Math.PI * 2)
        ctx.fillStyle = gradient
        ctx.fill()

        // Core dot
        ctx.beginPath()
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
        ctx.fillStyle = rgba(GOLD, isHovered ? 0.85 : 0.5)
        ctx.fill()

        // Pulse ring on hover — expands outward, fades
        if (isHovered) {
          node.pulseRingR = (node.pulseRingR ?? 0) + 0.7
          if (node.pulseRingR > 45) node.pulseRingR = 0
          const ringAlpha = Math.max(0, 0.6 - node.pulseRingR / 45 * 0.6)
          ctx.beginPath()
          ctx.arc(node.x, node.y, r + node.pulseRingR, 0, Math.PI * 2)
          ctx.strokeStyle = rgba(GOLD, ringAlpha)
          ctx.lineWidth   = 1
          ctx.stroke()
        } else {
          node.pulseRingR = 0
        }
      })

      rafRef.current = requestAnimationFrame(animate)
    }

    rafRef.current = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(rafRef.current)
      window.removeEventListener('resize', onResize)
    }
  }, [companies.length]) // re-init when company count changes

  // Don't render canvas on mobile
  if (typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches) {
    return null
  }

  return (
    <canvas
      ref={canvasRef}
      style={{
        position:      'fixed',
        inset:         0,
        zIndex:        -1,
        pointerEvents: 'none',
        display:       'block',
      }}
    />
  )
}

// ── Utility ──────────────────────────────────────────────────────────────────
function debounce(fn, ms) {
  let timer
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms) }
}
