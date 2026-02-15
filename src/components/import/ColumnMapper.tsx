"use client";

import { ColumnMapping } from "@/types";
import { CheckCircle2, AlertTriangle } from "lucide-react";

interface ColumnMapperProps {
  headers: string[];
  mapping: Partial<ColumnMapping>;
  onMappingChange: (mapping: Partial<ColumnMapping>) => void;
  preview: string[][];
}

const REQUIRED_FIELDS: { key: keyof ColumnMapping; label: string; required: boolean }[] = [
  { key: "date", label: "Date", required: true },
  { key: "ticker", label: "Ticker / Symbol", required: true },
  { key: "action", label: "Buy / Sell", required: true },
  { key: "quantity", label: "Quantity", required: true },
  { key: "price", label: "Price", required: true },
  { key: "total", label: "Total Amount", required: false },
];

export default function ColumnMapper({
  headers,
  mapping,
  onMappingChange,
  preview,
}: ColumnMapperProps) {
  const mappedCount = REQUIRED_FIELDS.filter(
    (f) => f.required && mapping[f.key],
  ).length;
  const requiredCount = REQUIRED_FIELDS.filter((f) => f.required).length;
  const allMapped = mappedCount === requiredCount;

  const handleChange = (field: keyof ColumnMapping, value: string) => {
    const updated = { ...mapping };
    if (value === "") {
      delete updated[field];
    } else {
      updated[field] = value;
    }
    onMappingChange(updated);
  };

  return (
    <div className="space-y-6">
      {/* Status */}
      <div
        className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
          allMapped
            ? "bg-gain-light text-gain"
            : "bg-accent-light text-accent"
        }`}
      >
        {allMapped ? (
          <CheckCircle2 className="w-4 h-4" />
        ) : (
          <AlertTriangle className="w-4 h-4" />
        )}
        {allMapped
          ? "All required columns mapped"
          : `${mappedCount} of ${requiredCount} required columns mapped`}
      </div>

      {/* Mapping Fields */}
      <div className="space-y-3">
        {REQUIRED_FIELDS.map((field) => (
          <div
            key={field.key}
            className="grid grid-cols-[140px_1fr] items-center gap-4"
          >
            <label className="text-sm text-text-secondary">
              {field.label}
              {field.required && <span className="text-loss ml-0.5">*</span>}
            </label>
            <select
              value={mapping[field.key] || ""}
              onChange={(e) => handleChange(field.key, e.target.value)}
              className={`
                w-full px-3 py-2 rounded-lg border text-sm bg-surface
                focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent
                ${
                  mapping[field.key]
                    ? "border-gain/30 text-text-primary"
                    : "border-border text-text-tertiary"
                }
              `}
            >
              <option value="">-- Select column --</option>
              {headers.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {/* Preview Table */}
      {preview.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
            Data Preview (first 5 rows)
          </p>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-surface-hover border-b border-border-light">
                  {headers.map((h) => (
                    <th
                      key={h}
                      className="px-3 py-2 text-left text-text-tertiary font-semibold whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.map((row, i) => (
                  <tr
                    key={i}
                    className="border-b border-border-light last:border-b-0"
                  >
                    {row.map((cell, j) => (
                      <td
                        key={j}
                        className="px-3 py-2 text-text-secondary whitespace-nowrap"
                      >
                        {cell || "-"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
