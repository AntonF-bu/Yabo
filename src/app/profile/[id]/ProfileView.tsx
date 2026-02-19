'use client'

import { useState, useRef, useEffect } from 'react'
import type {
  ProfileData,
  ProfileDimension,
  StatGroup,
  BiasData,
  SectorData,
} from './page'

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
/*  MAIN PROFILE VIEW                                                  */
/* ================================================================== */

interface Tab {
  key: string
  label: string
}

export default function ProfileView({ data }: { data: ProfileData }) {
  const [activeTab, setActiveTab] = useState('dna')
  const [activeDim, setActiveDim] = useState(0)
  const navRef = useRef<HTMLDivElement>(null)

  // Build tabs based on available data
  const tabs: Tab[] = []
  if (data.dimensions.length > 0) tabs.push({ key: 'dna', label: 'DNA' })
  if (data.entry) tabs.push({ key: 'entry', label: 'Entry' })
  if (data.exit) tabs.push({ key: 'exit', label: 'Exit' })
  if (data.timing) tabs.push({ key: 'timing', label: 'Timing' })
  if (data.psychology) tabs.push({ key: 'mind', label: 'Mind' })
  if (data.sectors.length > 0 || data.tickers.length > 0) tabs.push({ key: 'sectors', label: 'Sectors' })
  if (data.recommendation || data.behavioralDeepDive || data.riskPersonality) tabs.push({ key: 'action', label: 'Action' })

  // Default to first available tab
  useEffect(() => {
    if (tabs.length > 0 && !tabs.find(t => t.key === activeTab)) {
      setActiveTab(tabs[0].key)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Format stats ──
  const wr = data.stats.winRate
  const winRateStr = wr != null ? `${(wr <= 1 ? wr * 100 : wr).toFixed(1)}%` : '--'
  const pfStr = data.stats.profitFactor != null ? data.stats.profitFactor.toFixed(2) : '--'
  const holdStr = data.stats.avgHold != null ? `${Math.round(data.stats.avgHold)}d` : '--'
  const tradeStr = data.stats.trades != null ? String(data.stats.trades) : '--'

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

      {/* ── HERO ────────────────────────────────────────────────── */}
      <section style={{ padding: '40px 16px 0', textAlign: 'center' }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          {data.headline && (
            <h1 style={{
              fontFamily: F.display, fontSize: 'clamp(26px, 5vw, 40px)', fontWeight: 400,
              color: C.text, lineHeight: 1.15, letterSpacing: -0.5, margin: 0,
            }}>
              {data.headline}
            </h1>
          )}
          {data.behavioralSummary && (
            <p style={{
              fontFamily: F.display, fontSize: 'clamp(15px, 2.5vw, 18px)', fontStyle: 'italic',
              color: C.textSec, lineHeight: 1.5, margin: '12px auto 0', maxWidth: 520,
            }}>
              {data.behavioralSummary}
            </p>
          )}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
            {data.archetype && (
              <span style={{
                fontFamily: F.body, fontSize: 11, fontWeight: 500, color: C.text,
                padding: '4px 12px', border: `1px solid ${C.border}`, borderRadius: 20,
                textTransform: 'uppercase', letterSpacing: 1,
              }}>
                {data.archetype}
              </span>
            )}
            {data.tier && (
              <span style={{
                fontFamily: F.body, fontSize: 11, color: C.textSec,
                padding: '4px 12px', border: `1px solid ${C.border}`, borderRadius: 20,
                textTransform: 'uppercase', letterSpacing: 1,
              }}>
                {data.tier}
              </span>
            )}
          </div>
        </div>
      </section>

      {/* ── STATS STRIP ─────────────────────────────────────────── */}
      <section style={{ padding: '28px 16px 0' }}>
        <div style={{
          maxWidth: 720, margin: '0 auto',
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
        }}>
          {[
            { label: 'Win Rate', value: winRateStr },
            { label: 'Profit Factor', value: pfStr },
            { label: 'Avg Hold', value: holdStr },
            { label: 'Trades', value: tradeStr },
          ].map(s => (
            <div key={s.label} style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: F.mono, fontSize: 20, fontWeight: 700, color: C.gold }}>{s.value}</div>
              <div style={{ fontFamily: F.body, fontSize: 10, fontWeight: 500, color: C.textTer, textTransform: 'uppercase', letterSpacing: 1.2, marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>
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

        {/* ── ACTION TAB ──────────────────────────────────────── */}
        {activeTab === 'action' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <SectionTag>Insights & Recommendations</SectionTag>

            {/* Key recommendation callout */}
            {data.recommendation && (
              <Card style={{
                padding: '20px 24px',
                borderLeft: `3px solid ${C.gold}`,
                background: '#FBF7F0',
              }}>
                <div style={{ fontFamily: F.body, fontSize: 11, fontWeight: 600, letterSpacing: 2, color: C.textTer, textTransform: 'uppercase', marginBottom: 10 }}>
                  Key Recommendation
                </div>
                <Prose text={data.recommendation} />
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
          Analysis based on {data.meta.totalTrades || '--'} trades
          {data.meta.range ? ` from ${data.meta.range}` : ''}
        </p>
        <p style={{ fontFamily: F.body, fontSize: 12, color: C.textTer, margin: '4px 0 0' }}>
          Powered by Yabo Behavioral Mirror v0.5
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
        nav::-webkit-scrollbar {
          display: none;
        }
      `}</style>
    </main>
  )
}
