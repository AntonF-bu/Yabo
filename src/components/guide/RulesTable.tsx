"use client";

import { rulesTableData, tradeNote } from "@/lib/guide-content";

const statusStyles: Record<string, { text: string; label: string }> = {
  active: { text: "text-green font-semibold", label: "Active" },
  warning: { text: "text-teal font-semibold", label: "Active (warning only)" },
  future: { text: "text-text-ter", label: "Not yet (equities only in MVP)" },
};

export default function RulesTable() {
  return (
    <div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-2 pr-4 text-text-ter font-semibold text-xs font-body">Rule</th>
            <th className="text-left py-2 pr-4 text-text-ter font-semibold text-xs font-body">Constraint</th>
            <th className="text-left py-2 text-text-ter font-semibold text-xs font-body">Status</th>
          </tr>
        </thead>
        <tbody>
          {rulesTableData.map((row) => {
            const style = statusStyles[row.status];
            return (
              <tr key={row.rule} className="border-b border-border last:border-b-0">
                <td className="py-2.5 pr-4 text-[13px] font-semibold text-text font-body">{row.rule}</td>
                <td className="py-2.5 pr-4 text-[13px] text-text-sec font-body">{row.constraint}</td>
                <td className={`py-2.5 text-xs font-body ${style.text}`}>{style.label}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-xs text-text-ter font-body mt-4">{tradeNote}</p>
    </div>
  );
}
