'use client'

import { RuleCheck } from '@/lib/rules-engine'
import { CheckCircle, XCircle, AlertTriangle } from 'lucide-react'

interface RuleCheckListProps {
  checks: RuleCheck[]
}

export default function RuleCheckList({ checks }: RuleCheckListProps) {
  if (checks.length === 0) return null

  return (
    <div className="space-y-2">
      <p className="text-[10px] font-mono uppercase tracking-[2px] text-text-ter">
        Rules Check
      </p>
      {checks.map((check, i) => (
        <div
          key={i}
          className={`flex items-start gap-2.5 p-2.5 rounded-lg border ${
            !check.passed
              ? 'bg-red/5 border-red/20'
              : check.severity === 'warning'
                ? 'bg-yellow/5 border-yellow/20'
                : 'bg-teal/5 border-teal/20'
          }`}
        >
          {!check.passed ? (
            <XCircle className="w-4 h-4 text-red shrink-0 mt-0.5" />
          ) : check.severity === 'warning' ? (
            <AlertTriangle className="w-4 h-4 text-yellow shrink-0 mt-0.5" />
          ) : (
            <CheckCircle className="w-4 h-4 text-teal shrink-0 mt-0.5" />
          )}
          <div className="min-w-0">
            <p className={`text-xs font-semibold font-body ${
              !check.passed ? 'text-red' : check.severity === 'warning' ? 'text-yellow' : 'text-teal'
            }`}>
              {check.rule}
            </p>
            <p className="text-[11px] text-text-sec mt-0.5 font-body leading-relaxed">
              {check.message}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
