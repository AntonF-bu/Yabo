"use client";

import Link from "next/link";
import {
  Compass,
  MessageSquare,
  TrendingUp,
  LayoutGrid,
  Target,
  Lightbulb,
  Zap,
} from "lucide-react";

const tabs = [
  { id: "discover", label: "DISCOVER", icon: Compass },
  { id: "room", label: "ROOM", icon: MessageSquare },
  { id: "predict", label: "PREDICT", icon: TrendingUp },
  { id: "board", label: "BOARD", icon: LayoutGrid },
  { id: "mirror", label: "MIRROR", icon: Target },
  { id: "strategy", label: "STRATEGY", icon: Lightbulb },
  { id: "moves", label: "MOVES", icon: Zap },
];

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-[72px] bg-dark flex flex-col h-full">
      <div className="py-5 flex justify-center border-b border-dark-border">
        <Link href="/" className="block">
          <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center">
            <span className="text-sm font-bold text-white">Y</span>
          </div>
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
                    ? "text-accent"
                    : "text-white/40 hover:text-white/70"
                }
              `}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r bg-accent" />
              )}
              <Icon className="w-5 h-5" strokeWidth={isActive ? 2.5 : 1.5} />
              <span className="text-[8px] font-semibold tracking-wider">
                {tab.label}
              </span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
