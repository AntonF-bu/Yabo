'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import DimensionCard from './DimensionCard'

/* ================================================================== */
/*  Types                                                              */
/* ================================================================== */

interface DimensionSectionProps {
  profileId: string
}

interface ParsedDimension {
  key: string
  score: number
  label: string
  evidence: string[]
}

/* ================================================================== */
/*  Component                                                          */
/* ================================================================== */

export default function DimensionSection({ profileId }: DimensionSectionProps) {
  const [dimensions, setDimensions] = useState<ParsedDimension[] | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      const { data } = await supabase
        .from('analysis_results')
        .select('dimensions')
        .eq('profile_id', profileId)
        .eq('analysis_type', 'behavioral')
        .in('status', ['completed', 'partial'])
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (!data?.dimensions) {
        setDimensions([])
        return
      }

      // Parse JSONB (may arrive as string from some Supabase configs)
      const rawDims = typeof data.dimensions === 'string'
        ? JSON.parse(data.dimensions)
        : data.dimensions

      if (rawDims && typeof rawDims === 'object' && !Array.isArray(rawDims)) {
        const parsed: ParsedDimension[] = Object.entries(rawDims)
          .filter(([, v]) => v && typeof v === 'object')
          .map(([key, v]: [string, any]) => ({
            key,
            score: v.score ?? 50,
            label: v.label || '',
            evidence: v.evidence || [],
          }))
          .sort((a, b) => b.score - a.score)
        setDimensions(parsed)
      } else {
        setDimensions([])
      }
    }
    fetchData()
  }, [profileId])

  if (dimensions === null || dimensions.length === 0) return null

  return (
    <div style={{ marginBottom: 28 }}>
      {/* Section header */}
      <p style={{
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 11, fontWeight: 600, letterSpacing: 2,
        color: '#9A7B5B', textTransform: 'uppercase',
        margin: '0 0 12px',
      }}>
        Behavioral Dimensions
      </p>

      {/* Dimension cards grid */}
      <div className="dimension-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: 16,
      }}>
        {dimensions.map((dim) => (
          <DimensionCard
            key={dim.key}
            dimensionKey={dim.key}
            score={dim.score}
            label={dim.label}
            evidence={dim.evidence}
          />
        ))}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .dimension-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  )
}
