"use client";

import { tierTableData } from "@/lib/guide-content";

export default function TierTable() {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border">
          <th className="text-left py-2 pr-4 text-text-ter font-semibold text-xs font-body">Tier</th>
          <th className="text-left py-2 text-text-ter font-semibold text-xs font-body">Requirements</th>
        </tr>
      </thead>
      <tbody>
        {tierTableData.map((row) => (
          <tr key={row.tier} className="border-b border-border last:border-b-0">
            <td className="py-2.5 pr-4 text-[13px] font-semibold text-text font-body">{row.tier}</td>
            <td className="py-2.5 text-[13px] text-text-sec font-body">{row.requirements}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
