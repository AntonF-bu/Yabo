"use client";

import Link from "next/link";
import {
  Compass,
  MessageSquare,
  Target,
  BarChart3,
  ScanEye,
  Lightbulb,
  Zap,
  Upload,
} from "lucide-react";

const tabs = [
  { id: "discover", label: "DISCOVER", icon: Compass },
  { id: "room", label: "ROOM", icon: MessageSquare },
  { id: "predict", label: "PREDICT", icon: Target },
  { id: "board", label: "BOARD", icon: BarChart3 },
  { id: "mirror", label: "MIRROR", icon: ScanEye },
  { id: "strategy", label: "STRATEGY", icon: Lightbulb },
  { id: "moves", label: "MOVES", icon: Zap },
];

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-[72px] bg-bg flex flex-col h-full border-r border-border">
      <div className="py-5 flex justify-center border-b border-border">
        <Link href="/" className="block">
          <span className="font-display italic text-xl text-teal">Y</span>
        </Link>
      </div>

      <nav className="flex-1 py-4 flex flex-col items-center gap-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                w-14 flex flex-col items-center gap-1 py-2 rounded-lg
                transition-all duration-150 relative
                ${
                  isActive
                    ? "text-teal"
                    : "text-text-ter hover:text-text-sec"
                }
              `}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r bg-teal" />
              )}
              <Icon className="w-5 h-5" strokeWidth={isActive ? 2.5 : 1.5} />
              <span className="text-[9px] font-mono font-medium tracking-wider">
                {tab.label}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="py-4 flex justify-center border-t border-border">
        <Link
          href="/dashboard/import"
          className="w-14 flex flex-col items-center gap-1 py-2 rounded-lg text-text-ter hover:text-teal transition-all duration-150"
        >
          <Upload className="w-5 h-5" strokeWidth={1.5} />
          <span className="text-[9px] font-mono font-medium tracking-wider">IMPORT</span>
        </Link>
      </div>
    </aside>
  );
}
