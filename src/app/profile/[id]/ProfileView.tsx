'use client'

import { useState, useRef, useEffect } from 'react'
import type {
  ProfileData,
  ProfileDimension,
  StatGroup,
  BiasData,
  SectorData,
  PortfolioData,
} from './page'
import BehavioralRadar from './BehavioralRadar'
import DimensionSection from './DimensionSection'

/* ================================================================== */
/*  DESIGN TOKENS                                                      */
/* ================================================================== */

const C = {
  bg: '#F5F3EF',
  card: '#FFFFFF',
  border: '#E8E4DE',
  gold: '#B8860B',
  text: '#1A1715',
  textSec: '#8A8580',
  textTer: '#A09A94',
  textMuted: '#C5C0B8',
  highlight: '#FBF7F0',
  red: '#C45A4A',
}

const F = {
  display: "'Newsreader', Georgia, serif",
  body: "'Inter', system-ui, sans-serif",
  mono: "'IBM Plex Mono', monospace",
}

/* ================================================================== */
/*  PRIMITIVES                                                         */
/* ================================================================== */

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, ...style }}>
      {children}
    </div>
  )
}

function SectionTag({ children }: { children: React.ReactNode }) {
  return (
    <p style={{
      fontFamily: F.body, fontSize: 11, fontWeight: 600, letterSpacing: 3,
      color: C.textTer, textTransform: 'uppercase', margin: 0,
    }}>
      {children}
    </p>
  )
}

/* ================================================================== */
/*  COLLAPSIBLE GROUP                                                  */
/* ================================================================== */

function CollapsibleGroup({ title, subtitle, children, defaultOpen = true }: {
  title: string; subtitle: string; children: React.ReactNode; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', border: 'none', background: 'none', cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div>
          <div style={{ fontFamily: F.display, fontSize: 17, fontWeight: 500, color: C.text }}>{title}</div>
          <div style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, marginTop: 2 }}>{subtitle}</div>
        </div>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{
          transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease', flexShrink: 0, marginLeft: 12,
        }}>
          <path d="M5 8l5 5 5-5" stroke={C.textTer} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <div style={{
        maxHeight: open ? 2000 : 0, overflow: 'hidden',
        transition: 'max-height 0.35s ease',
      }}>
        <div style={{ padding: '0 20px 16px' }}>
          {children}
        </div>
      </div>
    </Card>
  )
}

/* ================================================================== */
/*  STAT ROW                                                           */
/* ================================================================== */

function StatRow({ v, l, h, why }: { v: string; l: string; h: boolean; why: string }) {
  const [open, setOpen] = useState(true)
  return (
    <div style={{ borderTop: `1px solid ${C.border}` }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 0', border: 'none', background: 'none', cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <span style={{
            fontFamily: F.mono, fontSize: 15, fontWeight: 600,
            color: h ? C.gold : C.text, flexShrink: 0,
          }}>
            {v}
          </span>
          <span style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {l}
          </span>
        </div>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{
          transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease', flexShrink: 0, marginLeft: 8,
        }}>
          <path d="M4 6l4 4 4-4" stroke={C.textMuted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && why && (
        <div style={{
          fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.6,
          padding: '0 0 12px', paddingLeft: 0,
        }}>
          {why}
        </div>
      )}
    </div>
  )
}

/* ================================================================== */
/*  RADAR CHART (SVG octagon)                                          */
/* ================================================================== */

function Radar({ dimensions, active, onSelect }: {
  dimensions: ProfileDimension[]; active: number; onSelect: (i: number) => void
}) {
  const size = 280
  const cx = size / 2
  const cy = size / 2
  const levels = [25, 50, 75, 100]
  const n = dimensions.length
  if (n === 0) return null

  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2
  const point = (i: number, r: number) => ({
    x: cx + (r / 100) * (size / 2 - 24) * Math.cos(angle(i)),
    y: cy + (r / 100) * (size / 2 - 24) * Math.sin(angle(i)),
  })

  const dataPoints = dimensions.map((d, i) => point(i, d.score))
  const polyStr = dataPoints.map(p => `${p.x},${p.y}`).join(' ')

  return (
    <svg viewBox={`0 0 ${size} ${size}`} style={{ width: '100%', maxWidth: size, display: 'block', margin: '0 auto' }}>
      {/* Grid levels */}
      {levels.map(lv => {
        const pts = dimensions.map((_, i) => point(i, lv))
        return (
          <polygon
            key={lv}
            points={pts.map(p => `${p.x},${p.y}`).join(' ')}
            fill="none" stroke={C.border} strokeWidth={lv === 50 ? 1 : 0.5}
            opacity={lv === 50 ? 0.8 : 0.4}
          />
        )
      })}

      {/* Axes */}
      {dimensions.map((_, i) => {
        const outer = point(i, 100)
        return <line key={i} x1={cx} y1={cy} x2={outer.x} y2={outer.y} stroke={C.border} strokeWidth={0.5} opacity={0.4} />
      })}

      {/* Data polygon */}
      <polygon points={polyStr} fill={C.gold} fillOpacity={0.12} stroke={C.gold} strokeWidth={1.5} />

      {/* Data points */}
      {dimensions.map((d, i) => {
        const p = dataPoints[i]
        const isActive = i === active
        return (
          <g key={d.key} style={{ cursor: 'pointer' }} onClick={() => onSelect(i)}>
            <circle cx={p.x} cy={p.y} r={isActive ? 7 : 5}
              fill={isActive ? C.gold : C.card} stroke={C.gold}
              strokeWidth={isActive ? 2 : 1.5}
              style={{ transition: 'r 0.2s ease, fill 0.2s ease' }}
            />
          </g>
        )
      })}

      {/* Labels */}
      {dimensions.map((d, i) => {
        const labelR = 108
        const p = point(i, labelR)
        const a = angle(i)
        const isLeft = Math.cos(a) < -0.3
        const isRight = Math.cos(a) > 0.3
        const anchor = isLeft ? 'end' : isRight ? 'start' : 'middle'
        const shortLabel = d.right
        return (
          <text key={d.key} x={p.x} y={p.y}
            textAnchor={anchor} dominantBaseline="middle"
            style={{
              fontFamily: F.body, fontSize: 10, fill: i === active ? C.text : C.textTer,
              fontWeight: i === active ? 600 : 400, cursor: 'pointer',
              transition: 'fill 0.2s ease',
            }}
            onClick={() => onSelect(i)}
          >
            {shortLabel}
          </text>
        )
      })}
    </svg>
  )
}

/* ================================================================== */
/*  DIMENSION DETAIL PANEL                                             */
/* ================================================================== */

function DimensionDetail({ dim }: { dim: ProfileDimension }) {
  const score = dim.score
  const pctLeft = Math.max(2, Math.min(98, score))
  return (
    <Card style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <span style={{ fontFamily: F.display, fontSize: 17, fontWeight: 500, color: C.text }}>{dim.label}</span>
        <span style={{ fontFamily: F.mono, fontSize: 20, fontWeight: 700, color: C.gold }}>{score}</span>
      </div>

      {/* Spectrum bar */}
      <div style={{ margin: '12px 0 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontFamily: F.body, fontSize: 11, color: C.textTer }}>{dim.left}</span>
          <span style={{ fontFamily: F.body, fontSize: 11, color: C.textTer }}>{dim.right}</span>
        </div>
        <div style={{ position: 'relative', height: 6, background: '#EDE9E3', borderRadius: 3 }}>
          <div style={{
            position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
            left: `${pctLeft}%`, width: 16, height: 16, borderRadius: '50%',
            background: C.gold, border: '3px solid white',
            boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
          }} />
        </div>
      </div>

      {/* Why */}
      {dim.why && (
        <p style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.6, margin: '12px 0 0' }}>
          {dim.why}
        </p>
      )}

      {/* Evidence details */}
      {dim.details.length > 0 && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
          gap: 8, marginTop: 14,
        }}>
          {dim.details.map((d, i) => (
            <div key={i} style={{
              background: C.highlight, borderRadius: 8, padding: '8px 10px',
            }}>
              {d.stat && (
                <div style={{ fontFamily: F.mono, fontSize: 11, fontWeight: 600, color: C.gold, marginBottom: 2 }}>
                  {d.stat}
                </div>
              )}
              <div style={{ fontFamily: F.body, fontSize: 11, color: C.textSec, lineHeight: 1.4 }}>
                {d.desc}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

/* ================================================================== */
/*  BIAS CARD                                                          */
/* ================================================================== */

function BiasCard({ bias }: { bias: BiasData }) {
  const [open, setOpen] = useState(false)
  const score = Math.min(100, Math.max(0, bias.score))
  const r = 28
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ

  return (
    <Card style={{ padding: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 14,
          border: 'none', background: 'none', cursor: 'pointer', textAlign: 'left', padding: 0,
        }}
      >
        {/* Circular gauge */}
        <svg width={64} height={64} viewBox="0 0 64 64" style={{ flexShrink: 0 }}>
          <circle cx={32} cy={32} r={r} fill="none" stroke="#EDE9E3" strokeWidth={5} />
          <circle cx={32} cy={32} r={r} fill="none" stroke={bias.color} strokeWidth={5}
            strokeDasharray={circ} strokeDashoffset={offset}
            strokeLinecap="round" transform="rotate(-90 32 32)"
            style={{ transition: 'stroke-dashoffset 0.5s ease' }}
          />
          <text x={32} y={32} textAnchor="middle" dominantBaseline="central"
            style={{ fontFamily: F.mono, fontSize: 14, fontWeight: 700, fill: C.text }}>
            {score.toFixed(0)}
          </text>
        </svg>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: F.body, fontSize: 14, fontWeight: 500, color: C.text }}>{bias.label}</div>
          <div style={{
            fontFamily: F.body, fontSize: 12, color: score > 50 ? C.red : score > 25 ? C.gold : '#4A8C6A',
            marginTop: 2,
          }}>
            {score > 50 ? 'High' : score > 25 ? 'Moderate' : 'Low'}
          </div>
        </div>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{
          transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease', flexShrink: 0,
        }}>
          <path d="M4 6l4 4 4-4" stroke={C.textMuted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && bias.why && (
        <div style={{
          fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.6,
          marginTop: 12, paddingTop: 12, borderTop: `1px solid ${C.border}`,
        }}>
          {bias.why}
        </div>
      )}
    </Card>
  )
}

/* ================================================================== */
/*  SECTOR BAR                                                         */
/* ================================================================== */

function SectorBar({ sectors }: { sectors: SectorData[] }) {
  if (sectors.length === 0) return null
  const max = Math.max(...sectors.map(s => s.pct), 1)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {sectors.map(s => (
        <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: F.body, fontSize: 13, color: C.text, width: 100, flexShrink: 0, textAlign: 'right' }}>
            {s.name}
          </span>
          <div style={{ flex: 1, height: 8, background: '#EDE9E3', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 4, background: s.color,
              width: `${(s.pct / max) * 100}%`,
              transition: 'width 0.5s ease',
            }} />
          </div>
          <span style={{ fontFamily: F.mono, fontSize: 12, color: C.textSec, width: 44, textAlign: 'right' }}>
            {s.pct.toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  )
}

/* ================================================================== */
/*  PROSE RENDERER                                                     */
/* ================================================================== */

function Prose({ text }: { text: string }) {
  const paragraphs = text.split(/\n\n+/).filter(Boolean)
  return (
    <div>
      {paragraphs.map((p, i) => (
        <p key={i} style={{
          fontFamily: F.body, fontSize: 15, color: C.text, lineHeight: 1.8,
          margin: 0, marginBottom: i < paragraphs.length - 1 ? 16 : 0,
        }}>
          {p.trim()}
        </p>
      ))}
    </div>
  )
}

/* ================================================================== */
/*  PORTFOLIO HELPERS                                                   */
/* ================================================================== */

function fmtDollar(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '--'
  if (n < 0) return `-$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function fmtPct(n: number | null | undefined, decimals = 1): string {
  if (n == null || isNaN(n)) return '--'
  return `${n.toFixed(decimals)}%`
}

function fmtRatio(n: number | null | undefined): string {
  if (n == null) return 'All'
  if (isNaN(n) || !isFinite(n)) return 'N/A'
  return `${n.toFixed(1)}x`
}

function hhi_label(hhi: number | null | undefined): string {
  if (hhi == null) return ''
  if (hhi > 0.25) return 'Concentrated'
  if (hhi > 0.15) return 'Moderate'
  return 'Diversified'
}

function SpectrumBar({ value, leftLabel, rightLabel }: {
  value: number | null | undefined; leftLabel: string; rightLabel: string
}) {
  const v = value != null && isFinite(value) ? Math.min(Math.max(value, 0), 100) : 50
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontFamily: F.body, fontSize: 11, color: C.textTer }}>{leftLabel}</span>
        <span style={{ fontFamily: F.body, fontSize: 11, color: C.textTer }}>{rightLabel}</span>
      </div>
      <div style={{ position: 'relative', height: 6, background: '#EDE9E3', borderRadius: 3 }}>
        <div style={{
          position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
          left: `${v}%`, width: 14, height: 14, borderRadius: '50%',
          background: C.gold, border: '3px solid white',
          boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
        }} />
      </div>
    </div>
  )
}

function AllocBar({ label, pctValue, dollarValue, maxPct, isLargest }: {
  label: string; pctValue: number; dollarValue?: string; maxPct: number; isLargest: boolean
}) {
  const barWidth = maxPct > 0 ? (pctValue / maxPct) * 100 : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{ fontFamily: F.body, fontSize: 13, color: C.text, width: 120, flexShrink: 0, textAlign: 'right' }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 8, background: '#EDE9E3', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 4,
          background: isLargest ? C.gold : '#C5B99B',
          width: `${barWidth}%`,
          transition: 'width 0.5s ease',
        }} />
      </div>
      <span style={{ fontFamily: F.mono, fontSize: 12, color: isLargest ? C.gold : C.textSec, width: 44, textAlign: 'right', fontWeight: isLargest ? 600 : 400 }}>
        {fmtPct(pctValue, 0)}
      </span>
      {dollarValue && (
        <span style={{ fontFamily: F.mono, fontSize: 11, color: C.textTer, width: 80, textAlign: 'right' }}>
          {dollarValue}
        </span>
      )}
    </div>
  )
}

function RiskBadge({ severity }: { severity: string }) {
  const s = severity?.toLowerCase()
  const color = s === 'high' ? C.red : s === 'moderate' ? C.gold : '#4A8C6A'
  return (
    <span style={{
      fontFamily: F.body, fontSize: 10, fontWeight: 600, color,
      textTransform: 'uppercase', letterSpacing: 1,
      padding: '2px 8px', borderRadius: 4,
      background: s === 'high' ? 'rgba(196,90,74,0.08)' : s === 'moderate' ? 'rgba(184,134,11,0.08)' : 'rgba(74,140,106,0.08)',
    }}>
      {severity}
    </span>
  )
}

/* ================================================================== */
/*  MAIN PROFILE VIEW                                                  */
/* ================================================================== */

interface Tab {
  key: string
  label: string
}

export default function ProfileView({ data, portfolioData, profileId }: { data: ProfileData; portfolioData?: PortfolioData; profileId: string }) {
  const [activeTab, setActiveTab] = useState('dna')
  const [activeDim, setActiveDim] = useState(0)
  const navRef = useRef<HTMLDivElement>(null)

  // Convenience accessors for portfolio data
  const pa = portfolioData?.portfolio_analysis ?? null
  const pf = portfolioData?.portfolio_features ?? null
  const hasPortfolio = !!(pa && typeof pa === 'object')

  // Build tabs based on available data
  const tabs: Tab[] = []
  if (data.dimensions.length > 0) tabs.push({ key: 'dna', label: 'DNA' })
  if (data.entry) tabs.push({ key: 'entry', label: 'Entry' })
  if (data.exit) tabs.push({ key: 'exit', label: 'Exit' })
  if (data.timing) tabs.push({ key: 'timing', label: 'Timing' })
  if (data.psychology) tabs.push({ key: 'mind', label: 'Mind' })
  if (data.sectors.length > 0 || data.tickers.length > 0) tabs.push({ key: 'sectors', label: 'Sectors' })
  if (hasPortfolio) tabs.push({ key: 'portfolio', label: 'Mirror' })
  if (data.recommendation || data.behavioralDeepDive || data.riskPersonality || hasPortfolio) tabs.push({ key: 'action', label: 'Action' })

  // Default to first available tab
  useEffect(() => {
    if (tabs.length > 0 && !tabs.find(t => t.key === activeTab)) {
      setActiveTab(tabs[0].key)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main style={{ minHeight: '100vh', background: C.bg }}>
      {/* ── HEADER ──────────────────────────────────────────────── */}
      <header style={{
        padding: '12px 16px', borderBottom: `1px solid ${C.border}`,
        position: 'sticky', top: 0, background: C.bg, zIndex: 50,
      }}>
        <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <a href="/" style={{ fontFamily: F.display, fontSize: 18, fontWeight: 600, color: C.text, textDecoration: 'none' }}>
            Yabo
          </a>
          {data.meta.range && (
            <span style={{ fontFamily: F.body, fontSize: 11, color: C.textTer }}>
              {data.meta.range}
            </span>
          )}
        </div>
      </header>

      {/* ── HERO: Behavioral Radar ────────────────────────────────── */}
      <section style={{ maxWidth: 720, margin: '0 auto' }}>
        <BehavioralRadar profileId={profileId} />
      </section>

      {/* ── NAV TABS ────────────────────────────────────────────── */}
      {tabs.length > 1 && (
        <nav ref={navRef} style={{
          position: 'sticky', top: 45, background: C.bg, zIndex: 40,
          borderBottom: `1px solid ${C.border}`, marginTop: 28,
          overflowX: 'auto', WebkitOverflowScrolling: 'touch',
        }}>
          <div style={{
            maxWidth: 720, margin: '0 auto', display: 'flex', gap: 0,
            padding: '0 16px', minWidth: 'min-content',
          }}>
            {tabs.map(tab => {
              const isActive = tab.key === activeTab
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    fontFamily: F.body, fontSize: 13, fontWeight: isActive ? 600 : 400,
                    color: isActive ? C.text : C.textTer,
                    background: 'none', border: 'none', cursor: 'pointer',
                    padding: '12px 16px',
                    borderBottom: isActive ? `2px solid ${C.gold}` : '2px solid transparent',
                    transition: 'color 0.15s ease, border-color 0.15s ease',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {tab.label}
                </button>
              )
            })}
          </div>
        </nav>
      )}

      {/* ── TAB CONTENT ─────────────────────────────────────────── */}
      <div style={{ maxWidth: 720, margin: '0 auto', padding: '24px 16px 80px' }}>

        {/* ── DNA TAB ─────────────────────────────────────────── */}
        {activeTab === 'dna' && data.dimensions.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <SectionTag>Your Trading DNA</SectionTag>

            {/* Radar + Detail: side-by-side on desktop, stacked on mobile */}
            <div className="radar-grid" style={{ display: 'grid', gap: 16, alignItems: 'start' }}>
              <Card style={{ padding: 16 }}>
                <Radar dimensions={data.dimensions} active={activeDim} onSelect={setActiveDim} />
              </Card>
              {data.dimensions[activeDim] && (
                <DimensionDetail dim={data.dimensions[activeDim]} />
              )}
            </div>

            {/* All dimensions list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.dimensions.map((dim, i) => (
                <button
                  key={dim.key}
                  onClick={() => setActiveDim(i)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
                    background: i === activeDim ? C.card : 'transparent',
                    border: i === activeDim ? `1px solid ${C.border}` : '1px solid transparent',
                    borderRadius: 8, cursor: 'pointer', textAlign: 'left', width: '100%',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <span style={{ fontFamily: F.mono, fontSize: 14, fontWeight: 700, color: C.gold, width: 28 }}>
                    {dim.score}
                  </span>
                  <span style={{ fontFamily: F.body, fontSize: 13, color: C.text, flex: 1 }}>
                    {dim.label}
                  </span>
                  <span style={{ fontFamily: F.body, fontSize: 11, color: C.textTer }}>
                    {dim.left} / {dim.right}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── ENTRY TAB ───────────────────────────────────────── */}
        {activeTab === 'entry' && data.entry && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <SectionTag>Entry Analysis</SectionTag>
            {data.entry.groups.map((g, gi) => (
              <CollapsibleGroup key={gi} title={g.title} subtitle={g.subtitle}>
                {g.items.map((item, ii) => (
                  <StatRow key={ii} v={item.v} l={item.l} h={item.h} why={item.why} />
                ))}
              </CollapsibleGroup>
            ))}
          </div>
        )}

        {/* ── EXIT TAB ────────────────────────────────────────── */}
        {activeTab === 'exit' && data.exit && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <SectionTag>Exit Analysis</SectionTag>
            {data.exit.groups.map((g, gi) => (
              <CollapsibleGroup key={gi} title={g.title} subtitle={g.subtitle}>
                {g.items.map((item, ii) => (
                  <StatRow key={ii} v={item.v} l={item.l} h={item.h} why={item.why} />
                ))}
              </CollapsibleGroup>
            ))}
          </div>
        )}

        {/* ── TIMING TAB ──────────────────────────────────────── */}
        {activeTab === 'timing' && data.timing && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <SectionTag>Timing Analysis</SectionTag>
            {data.timing.groups.map((g, gi) => (
              <CollapsibleGroup key={gi} title={g.title} subtitle={g.subtitle}>
                {g.items.map((item, ii) => (
                  <StatRow key={ii} v={item.v} l={item.l} h={item.h} why={item.why} />
                ))}
              </CollapsibleGroup>
            ))}

            {/* Hold distribution */}
            {data.holds.length > 0 && (
              <CollapsibleGroup title="Holding Periods" subtitle="How long you hold positions">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {data.holds.map(h => {
                    const maxH = Math.max(...data.holds.map(x => x.pct), 1)
                    return (
                      <div key={h.range} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontFamily: F.body, fontSize: 12, color: C.textSec, width: 70, textAlign: 'right', flexShrink: 0 }}>
                          {h.range}
                        </span>
                        <div style={{ flex: 1, height: 6, background: '#EDE9E3', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', borderRadius: 3, background: C.gold,
                            width: `${(h.pct / maxH) * 100}%`,
                          }} />
                        </div>
                        <span style={{ fontFamily: F.mono, fontSize: 11, color: C.textTer, width: 28, textAlign: 'right' }}>
                          {h.pct}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </CollapsibleGroup>
            )}
          </div>
        )}

        {/* ── MIND TAB ────────────────────────────────────────── */}
        {activeTab === 'mind' && data.psychology && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <SectionTag>Psychology & Biases</SectionTag>

            {/* Bias cards grid */}
            {data.psychology.biases.length > 0 && (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: 12,
              }}>
                {data.psychology.biases.map(b => (
                  <BiasCard key={b.key} bias={b} />
                ))}
              </div>
            )}

            {/* Stat groups */}
            {data.psychology.groups.map((g, gi) => (
              <CollapsibleGroup key={gi} title={g.title} subtitle={g.subtitle}>
                {g.items.map((item, ii) => (
                  <StatRow key={ii} v={item.v} l={item.l} h={item.h} why={item.why} />
                ))}
              </CollapsibleGroup>
            ))}
          </div>
        )}

        {/* ── SECTORS TAB ─────────────────────────────────────── */}
        {activeTab === 'sectors' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <SectionTag>Portfolio Concentration</SectionTag>

            {data.sectors.length > 0 && (
              <CollapsibleGroup title="Sector Allocation" subtitle="Where your capital is deployed">
                <SectorBar sectors={data.sectors} />
              </CollapsibleGroup>
            )}

            {data.tickers.length > 0 && (
              <CollapsibleGroup title="Top Tickers" subtitle="Most traded names">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {data.tickers.map(t => {
                    const maxW = Math.max(...data.tickers.map(x => x.weight), 1)
                    return (
                      <div key={t.name} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 600, color: C.text, width: 60, flexShrink: 0, textAlign: 'right' }}>
                          {t.name}
                        </span>
                        <div style={{ flex: 1, height: 6, background: '#EDE9E3', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', borderRadius: 3, background: C.gold,
                            width: `${(t.weight / maxW) * 100}%`,
                          }} />
                        </div>
                        <span style={{ fontFamily: F.mono, fontSize: 11, color: C.textTer, width: 40, textAlign: 'right' }}>
                          {t.weight.toFixed(0)}%
                        </span>
                        {t.trades > 0 && (
                          <span style={{ fontFamily: F.body, fontSize: 11, color: C.textMuted, width: 50 }}>
                            {t.trades} trades
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </CollapsibleGroup>
            )}
          </div>
        )}

        {/* ── MIRROR TAB (was Portfolio) ─────────────────────── */}
        {activeTab === 'portfolio' && hasPortfolio && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Behavioral Dimension Cards (above portfolio content) */}
            <DimensionSection profileId={profileId} />

            <SectionTag>Portfolio Analysis</SectionTag>

            {/* ── SECTION 1: OVERVIEW ─────────────────────── */}
            <CollapsibleGroup title="Portfolio Overview" subtitle="Asset summary and account structure" defaultOpen={true}>
              {/* Hero stat strip */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
                gap: 8, marginBottom: 16,
              }}>
                {[
                  { label: 'Total Value', value: fmtDollar(pf?.equity_pct != null ? (portfolioData?.reconstructed_holdings as any)?._total_estimated_value : null) || fmtDollar(
                    // Sum from allocation percentages and features
                    pf?.muni_face_value && pf?.fixed_income_pct
                      ? (pf.muni_face_value / (pf.fixed_income_pct / 100))
                      : null
                  ) },
                  { label: 'Accounts', value: portfolioData?.accounts_detected?.length?.toString() ?? '--' },
                  { label: 'Annual Yield', value: fmtPct(pf?.estimated_portfolio_yield) },
                  { label: 'Fee Drag', value: fmtPct(pf?.fee_drag_pct) },
                  { label: 'Tax Score', value: pf?.tax_placement_score != null ? `${pf.tax_placement_score}/100` : '--' },
                ].map(s => (
                  <div key={s.label} style={{ textAlign: 'center', padding: '8px 4px' }}>
                    <div style={{ fontFamily: F.mono, fontSize: 17, fontWeight: 700, color: C.gold }}>{s.value}</div>
                    <div style={{ fontFamily: F.body, fontSize: 10, fontWeight: 500, color: C.textTer, textTransform: 'uppercase', letterSpacing: 1.2, marginTop: 2 }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Headline */}
              {pa?.portfolio_structure?.headline && (
                <h2 style={{
                  fontFamily: F.display, fontSize: 20, fontWeight: 400,
                  color: C.text, lineHeight: 1.4, margin: '0 0 16px',
                }}>
                  {pa.portfolio_structure.headline}
                </h2>
              )}

              {/* Account purpose cards */}
              {pa?.portfolio_structure?.account_purposes?.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
                  {pa.portfolio_structure.account_purposes.map((acct: any, i: number) => (
                    <div key={i} style={{
                      background: C.highlight, borderRadius: 8, padding: '12px 14px',
                      display: 'flex', alignItems: 'flex-start', gap: 12,
                    }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <span style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 600, color: C.text }}>
                            {acct.account_id || `Account ${i + 1}`}
                          </span>
                          {acct.account_type && (
                            <span style={{
                              fontFamily: F.body, fontSize: 10, fontWeight: 500, color: C.gold,
                              padding: '2px 8px', border: `1px solid ${C.gold}`, borderRadius: 10,
                              textTransform: 'uppercase', letterSpacing: 0.5,
                            }}>
                              {acct.account_type}
                            </span>
                          )}
                        </div>
                        <div style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.5 }}>
                          {acct.purpose}{acct.strategy ? ` — ${acct.strategy}` : ''}
                        </div>
                      </div>
                      {acct.estimated_value && (
                        <span style={{ fontFamily: F.mono, fontSize: 14, fontWeight: 600, color: C.text, flexShrink: 0 }}>
                          {acct.estimated_value}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Narrative */}
              {pa?.portfolio_structure?.narrative && <Prose text={pa.portfolio_structure.narrative} />}
            </CollapsibleGroup>

            {/* ── SECTION 2: CONCENTRATION ─────────────────── */}
            {pa?.concentration_analysis && (
              <CollapsibleGroup title="Concentration" subtitle="Position and sector concentration risk" defaultOpen={false}>
                {pa.concentration_analysis.headline && (
                  <h3 style={{
                    fontFamily: F.display, fontSize: 17, fontWeight: 400,
                    color: C.text, lineHeight: 1.4, margin: '0 0 14px',
                  }}>
                    {pa.concentration_analysis.headline}
                  </h3>
                )}

                {/* Concentration stats grid */}
                {pf && (
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 8, marginBottom: 14,
                  }} className="portfolio-stat-grid">
                    {[
                      { label: 'Ticker HHI', value: pf.ticker_hhi?.toFixed(3) ?? '--', note: hhi_label(pf.ticker_hhi) },
                      { label: 'Sector HHI', value: pf.sector_hhi?.toFixed(3) ?? '--', note: hhi_label(pf.sector_hhi) },
                      { label: 'Top Position', value: fmtPct(pf.top1_concentration), note: '' },
                      { label: 'Top 3', value: fmtPct(pf.top3_concentration), note: '' },
                      { label: 'Top 5', value: fmtPct(pf.top5_concentration), note: '' },
                      { label: 'Cross-account max', value: fmtPct(pf.max_cross_account_exposure), note: '' },
                    ].map(s => (
                      <div key={s.label} style={{
                        background: C.highlight, borderRadius: 8, padding: '10px 12px',
                      }}>
                        <div style={{ fontFamily: F.mono, fontSize: 15, fontWeight: 600, color: C.gold }}>
                          {s.value}
                        </div>
                        <div style={{ fontFamily: F.body, fontSize: 11, color: C.textSec, marginTop: 2 }}>
                          {s.label}{s.note ? ` — ${s.note}` : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Top exposures */}
                {pa.concentration_analysis.top_exposures?.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                    {pa.concentration_analysis.top_exposures.slice(0, 8).map((exp: any, i: number) => (
                      <div key={i} style={{
                        borderTop: i > 0 ? `1px solid ${C.border}` : 'none',
                        padding: '10px 0',
                        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8,
                      }}>
                        <div>
                          <span style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 600, color: C.text }}>
                            {exp.name}
                          </span>
                          {exp.includes && (
                            <span style={{ fontFamily: F.body, fontSize: 11, color: C.textTer, marginLeft: 6 }}>
                              ({exp.includes})
                            </span>
                          )}
                        </div>
                        <span style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 600, color: C.gold, flexShrink: 0 }}>
                          {exp.total_exposure || exp.percentage || ''}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {pa.concentration_analysis.narrative && (
                  <div style={{ marginTop: 12 }}>
                    <Prose text={pa.concentration_analysis.narrative} />
                  </div>
                )}
              </CollapsibleGroup>
            )}

            {/* ── SECTION 3: ASSET ALLOCATION ─────────────── */}
            {pf && (
              <CollapsibleGroup title="Asset Allocation" subtitle="Portfolio structure by asset type" defaultOpen={false}>
                {(() => {
                  const allocItems = [
                    { label: 'Equities', pct: pf.equity_pct ?? 0 },
                    { label: 'Fixed Income', pct: pf.fixed_income_pct ?? 0 },
                    { label: 'ETFs', pct: pf.etf_pct ?? 0 },
                    { label: 'Options', pct: pf.options_pct ?? 0 },
                    { label: 'Structured', pct: pf.structured_pct ?? 0 },
                    { label: 'Cash', pct: pf.cash_pct ?? 0 },
                  ].filter(a => a.pct > 0)
                  const maxPct = Math.max(...allocItems.map(a => a.pct), 1)
                  const largestPct = Math.max(...allocItems.map(a => a.pct))
                  return (
                    <>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {allocItems.map(a => (
                          <AllocBar
                            key={a.label}
                            label={a.label}
                            pctValue={a.pct}
                            maxPct={maxPct}
                            isLargest={a.pct === largestPct}
                          />
                        ))}
                      </div>

                      {/* Active/Passive spectrum */}
                      <div style={{ marginTop: 20 }}>
                        <div style={{ fontFamily: F.body, fontSize: 12, fontWeight: 500, color: C.textSec, marginBottom: 2 }}>
                          Active vs Passive {pf.active_vs_passive != null ? `(${fmtRatio(pf.active_vs_passive)} active)` : ''}
                        </div>
                        <SpectrumBar
                          value={pf.active_vs_passive != null
                            ? Math.min(95, (pf.active_vs_passive / (1 + pf.active_vs_passive)) * 100)
                            : 95
                          }
                          leftLabel="Passive"
                          rightLabel="Active"
                        />
                      </div>

                      {/* Single name vs ETF */}
                      <div style={{ marginTop: 16 }}>
                        <div style={{ fontFamily: F.body, fontSize: 12, fontWeight: 500, color: C.textSec, marginBottom: 2 }}>
                          Single Stocks vs ETFs {pf.single_name_vs_etf_ratio != null ? `(${fmtRatio(pf.single_name_vs_etf_ratio)} stocks)` : ''}
                        </div>
                        <SpectrumBar
                          value={pf.single_name_vs_etf_ratio != null
                            ? Math.min(95, (pf.single_name_vs_etf_ratio / (1 + pf.single_name_vs_etf_ratio)) * 100)
                            : 95
                          }
                          leftLabel="ETF-heavy"
                          rightLabel="Stock-heavy"
                        />
                      </div>
                    </>
                  )
                })()}
              </CollapsibleGroup>
            )}

            {/* ── SECTION 4: INCOME & FEES ────────────────── */}
            {pa?.income_analysis && (
              <CollapsibleGroup title="Income & Fees" subtitle="Yield, fee drag, and tax context" defaultOpen={false}>
                {pa.income_analysis.headline && (
                  <h3 style={{
                    fontFamily: F.display, fontSize: 17, fontWeight: 400,
                    color: C.text, lineHeight: 1.4, margin: '0 0 14px',
                  }}>
                    {pa.income_analysis.headline}
                  </h3>
                )}

                {/* Income stats */}
                {pf && (
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 8, marginBottom: 14,
                  }} className="portfolio-stat-grid">
                    {[
                      { label: 'Gross Dividends', value: fmtDollar(pf.gross_dividend_income) },
                      { label: 'Gross Interest', value: fmtDollar(pf.gross_interest_income) },
                      { label: 'Total Fees', value: fmtDollar(pf.total_fees) },
                      { label: 'Net Income', value: fmtDollar(pf.net_income_after_fees) },
                      { label: 'Portfolio Yield', value: fmtPct(pf.estimated_portfolio_yield) },
                      { label: 'Fee Drag', value: fmtPct(pf.fee_drag_pct, 2) },
                    ].map(s => (
                      <div key={s.label} style={{
                        background: C.highlight, borderRadius: 8, padding: '10px 12px',
                      }}>
                        <div style={{ fontFamily: F.mono, fontSize: 15, fontWeight: 600, color: C.gold }}>{s.value}</div>
                        <div style={{ fontFamily: F.body, fontSize: 11, color: C.textSec, marginTop: 2 }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Income concentration note */}
                {pf?.income_concentration_top3 != null && (
                  <p style={{
                    fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.6,
                    margin: '0 0 12px', padding: '8px 12px', background: C.highlight, borderRadius: 8,
                  }}>
                    {fmtPct(pf.income_concentration_top3, 0)} of your dividend income comes from 3 sources.
                  </p>
                )}

                {pa.income_analysis.narrative && <Prose text={pa.income_analysis.narrative} />}

                {/* Tax context callout */}
                {pa?.tax_context?.detected_jurisdiction && (
                  <div style={{
                    marginTop: 16, padding: '16px 20px',
                    background: '#FBF7F0', borderLeft: `3px solid ${C.gold}`, borderRadius: 8,
                  }}>
                    <div style={{ fontFamily: F.body, fontSize: 11, fontWeight: 600, letterSpacing: 2, color: C.textTer, textTransform: 'uppercase', marginBottom: 8 }}>
                      Tax Jurisdiction
                    </div>
                    <div style={{ fontFamily: F.display, fontSize: 17, fontWeight: 500, color: C.text, marginBottom: 6 }}>
                      Detected: {pa.tax_context.detected_jurisdiction} resident
                    </div>
                    {pa.tax_context.evidence && (
                      <p style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.6, margin: '0 0 8px' }}>
                        {pa.tax_context.evidence}
                      </p>
                    )}
                    {pf?.tax_placement_score != null && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                        <span style={{ fontFamily: F.body, fontSize: 12, color: C.textSec }}>Tax placement score:</span>
                        <span style={{ fontFamily: F.mono, fontSize: 14, fontWeight: 700, color: C.gold }}>{pf.tax_placement_score}/100</span>
                      </div>
                    )}
                    {pa.tax_context.narrative && (
                      <div style={{ marginTop: 10 }}>
                        <Prose text={pa.tax_context.narrative} />
                      </div>
                    )}
                  </div>
                )}
              </CollapsibleGroup>
            )}

            {/* ── SECTION 5: OPTIONS & STRUCTURED ─────────── */}
            {(pa?.options_strategy || (pf?.structured_product_exposure != null && pf.structured_product_exposure > 0)) && (
              <CollapsibleGroup title="Options & Structured" subtitle="Derivatives exposure and strategy" defaultOpen={false}>
                {pa?.options_strategy?.headline && (
                  <h3 style={{
                    fontFamily: F.display, fontSize: 17, fontWeight: 400,
                    color: C.text, lineHeight: 1.4, margin: '0 0 14px',
                  }}>
                    {pa.options_strategy.headline}
                  </h3>
                )}

                {/* Options key stats */}
                {pf && (pf.options_premium_at_risk > 0 || pf.options_notional_exposure > 0) && (
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 8, marginBottom: 14,
                  }} className="portfolio-stat-grid">
                    {[
                      { label: 'Premium at Risk', value: fmtDollar(pf.options_premium_at_risk) },
                      { label: 'Notional Exposure', value: fmtDollar(pf.options_notional_exposure), highlight: true },
                    ].map(s => (
                      <div key={s.label} style={{
                        background: C.highlight, borderRadius: 8, padding: '10px 12px',
                      }}>
                        <div style={{ fontFamily: F.mono, fontSize: s.highlight ? 18 : 15, fontWeight: 700, color: C.gold }}>{s.value}</div>
                        <div style={{ fontFamily: F.body, fontSize: 11, color: C.textSec, marginTop: 2 }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                )}

                {pa?.options_strategy?.narrative && <Prose text={pa.options_strategy.narrative} />}

                {/* Structured products sub-section */}
                {pf?.structured_product_exposure != null && pf.structured_product_exposure > 0 && (
                  <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                    <div style={{ fontFamily: F.body, fontSize: 12, fontWeight: 500, color: C.textSec, marginBottom: 6 }}>
                      Structured Products
                    </div>
                    <div style={{ fontFamily: F.mono, fontSize: 17, fontWeight: 700, color: C.gold }}>
                      {fmtDollar(pf.structured_product_exposure)}
                    </div>
                    <p style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.6, margin: '6px 0 0' }}>
                      Structured note exposure carries counterparty risk tied to the issuing institution.
                    </p>
                  </div>
                )}
              </CollapsibleGroup>
            )}

            {/* ── SECTION 6: RISK ASSESSMENT ──────────────── */}
            {pa?.risk_assessment && (
              <CollapsibleGroup title="Risk Assessment" subtitle="Drawdown sensitivity, concentration, and key risks" defaultOpen={false}>
                {pa.risk_assessment.headline && (
                  <h3 style={{
                    fontFamily: F.display, fontSize: 17, fontWeight: 400,
                    color: C.text, lineHeight: 1.4, margin: '0 0 14px',
                  }}>
                    {pa.risk_assessment.headline}
                  </h3>
                )}

                {/* Drawdown callout */}
                {pf?.drawdown_sensitivity != null && (
                  <div style={{
                    padding: '16px 20px', background: 'rgba(196,90,74,0.04)',
                    borderLeft: `3px solid ${C.red}`, borderRadius: 8, marginBottom: 14,
                  }}>
                    <div style={{ fontFamily: F.body, fontSize: 11, fontWeight: 600, letterSpacing: 2, color: C.textTer, textTransform: 'uppercase', marginBottom: 6 }}>
                      20% Market Decline Impact
                    </div>
                    <div style={{ fontFamily: F.mono, fontSize: 24, fontWeight: 700, color: C.red }}>
                      ~{fmtDollar(pf.drawdown_sensitivity)}
                    </div>
                    <p style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.5, margin: '6px 0 0' }}>
                      Beta-weighted estimate of portfolio loss in a broad market 20% decline.
                    </p>
                  </div>
                )}

                {/* Largest loss potential */}
                {pf?.largest_loss_potential != null && (
                  <div style={{
                    background: C.highlight, borderRadius: 8, padding: '12px 14px', marginBottom: 14,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <span style={{ fontFamily: F.body, fontSize: 13, color: C.textSec }}>
                      Largest single-position exposure
                    </span>
                    <span style={{ fontFamily: F.mono, fontSize: 15, fontWeight: 600, color: C.text }}>
                      {fmtDollar(pf.largest_loss_potential)}
                    </span>
                  </div>
                )}

                {/* Correlation estimate */}
                {pf?.correlation_estimate != null && (
                  <div style={{
                    background: C.highlight, borderRadius: 8, padding: '12px 14px', marginBottom: 14,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <span style={{ fontFamily: F.body, fontSize: 13, color: C.textSec }}>
                      Portfolio correlation estimate
                    </span>
                    <span style={{ fontFamily: F.mono, fontSize: 15, fontWeight: 600, color: pf.correlation_estimate > 0.6 ? C.gold : C.text }}>
                      {pf.correlation_estimate.toFixed(2)}
                    </span>
                  </div>
                )}

                {/* Key risks */}
                {pa.risk_assessment.key_risks?.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
                    {pa.risk_assessment.key_risks.map((risk: any, i: number) => (
                      <div key={i} style={{
                        background: C.highlight, borderRadius: 8, padding: '12px 14px',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                          {risk.severity && <RiskBadge severity={risk.severity} />}
                          <span style={{ fontFamily: F.body, fontSize: 13, fontWeight: 500, color: C.text }}>
                            {risk.risk}
                          </span>
                        </div>
                        {risk.detail && (
                          <p style={{ fontFamily: F.body, fontSize: 13, color: C.textSec, lineHeight: 1.5, margin: 0 }}>
                            {risk.detail}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {pa.risk_assessment.narrative && <Prose text={pa.risk_assessment.narrative} />}
              </CollapsibleGroup>
            )}

            {/* ── KEY RECOMMENDATION (bottom) ─────────────── */}
            {pa?.key_recommendation && (
              <Card style={{
                padding: '20px 24px',
                borderLeft: `3px solid ${C.gold}`,
                background: '#FBF7F0',
              }}>
                <div style={{ fontFamily: F.body, fontSize: 11, fontWeight: 600, letterSpacing: 2, color: C.textTer, textTransform: 'uppercase', marginBottom: 10 }}>
                  Portfolio Recommendation
                </div>
                <Prose text={pa.key_recommendation} />
              </Card>
            )}
          </div>
        )}

        {/* ── ACTION TAB ──────────────────────────────────────── */}
        {activeTab === 'action' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <SectionTag>Insights & Recommendations</SectionTag>

            {/* Data coverage disclaimer */}
            <div style={{
              fontFamily: F.body, fontSize: 13, color: '#8A8580', fontStyle: 'italic',
              borderLeft: '3px solid #9A7B5B', padding: 16, marginBottom: 24,
              lineHeight: 1.6,
            }}>
              Analysis based on trading activity from CSV data only. Positions
              without activity during the imported date range may not be reflected.
              Full portfolio analysis requires holdings import.
            </div>

            {/* Behavioral recommendation callout */}
            {data.recommendation && (
              <Card style={{
                padding: '20px 24px',
                borderLeft: `3px solid ${C.gold}`,
                background: '#FBF7F0',
              }}>
                <div style={{ fontFamily: F.body, fontSize: 11, fontWeight: 600, letterSpacing: 2, color: C.textTer, textTransform: 'uppercase', marginBottom: 10 }}>
                  {hasPortfolio ? 'Behavioral Recommendation' : 'Key Recommendation'}
                </div>
                <Prose text={data.recommendation} />
              </Card>
            )}

            {/* Portfolio recommendation callout (when portfolio data exists) */}
            {hasPortfolio && pa?.key_recommendation && (
              <Card style={{
                padding: '20px 24px',
                borderLeft: `3px solid ${C.gold}`,
                background: '#FBF7F0',
              }}>
                <div style={{ fontFamily: F.body, fontSize: 11, fontWeight: 600, letterSpacing: 2, color: C.textTer, textTransform: 'uppercase', marginBottom: 10 }}>
                  Portfolio Recommendation
                </div>
                <Prose text={pa.key_recommendation} />
              </Card>
            )}

            {/* Behavioral deep dive */}
            {data.behavioralDeepDive && (
              <CollapsibleGroup title="Behavioral Analysis" subtitle="Deep dive into your trading patterns">
                <Prose text={data.behavioralDeepDive} />
              </CollapsibleGroup>
            )}

            {/* Risk personality */}
            {data.riskPersonality && (
              <CollapsibleGroup title="Risk Personality" subtitle="How you manage risk and drawdowns">
                <Prose text={data.riskPersonality} />
              </CollapsibleGroup>
            )}

            {/* Tax efficiency */}
            {data.taxEfficiency && (
              <CollapsibleGroup title="Tax Efficiency" subtitle="Tax-related patterns in your trading">
                <Prose text={data.taxEfficiency} />
              </CollapsibleGroup>
            )}
          </div>
        )}
      </div>

      {/* ── FOOTER ──────────────────────────────────────────────── */}
      <footer style={{
        borderTop: `1px solid ${C.border}`, padding: '20px 16px',
        textAlign: 'center',
      }}>
        <p style={{ fontFamily: F.body, fontSize: 12, color: C.textTer, margin: 0 }}>
          Powered by Yabo
        </p>
      </footer>

      {/* ── RESPONSIVE STYLES ───────────────────────────────────── */}
      <style>{`
        .radar-grid {
          grid-template-columns: minmax(200px, 280px) 1fr;
        }
        @media (max-width: 640px) {
          .radar-grid {
            grid-template-columns: 1fr !important;
          }
        }
        @media (max-width: 480px) {
          .portfolio-stat-grid {
            grid-template-columns: 1fr !important;
          }
        }
        nav::-webkit-scrollbar {
          display: none;
        }
      `}</style>
    </main>
  )
}
