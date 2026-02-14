"use client";

import { useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Brain,
  Lightbulb,
  Users,
  Trophy,
} from "lucide-react";

const tabs = [
  { id: "room", label: "The Room", icon: MessageSquare },
  { id: "dna", label: "Trading DNA", icon: Brain },
  { id: "strategy", label: "Strategy", icon: Lightbulb },
  { id: "moves", label: "The Move", icon: Users },
  { id: "leaderboard", label: "Leaderboard", icon: Trophy },
];

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-56 border-r border-border bg-surface flex flex-col h-full">
      <div className="p-5 border-b border-border">
        <Link href="/" className="block">
          <h1 className="text-xl font-bold text-text-primary tracking-tight">
            Yabo
          </h1>
        </Link>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                transition-all duration-150
                ${
                  isActive
                    ? "bg-accent-light text-accent"
                    : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                }
              `}
            >
              <Icon className="w-4.5 h-4.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="px-3 py-2 rounded-lg bg-background">
          <p className="text-xs text-text-tertiary">Season 1</p>
          <p className="text-sm font-medium text-text-primary">Week 12 of 16</p>
          <div className="mt-2 h-1.5 bg-border-light rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: "75%" }}
            />
          </div>
        </div>
      </div>
    </aside>
  );
}
