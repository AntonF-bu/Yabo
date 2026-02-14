"use client";

import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import RoomFeed from "@/components/dashboard/RoomFeed";
import Leaderboard from "@/components/dashboard/Leaderboard";
import TradingDNA from "@/components/dashboard/TradingDNA";
import StrategyTab from "@/components/dashboard/StrategyTab";
import MovesTab from "@/components/dashboard/MovesTab";
import { Menu, X } from "lucide-react";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState("room");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const renderContent = () => {
    switch (activeTab) {
      case "room":
        return (
          <div className="flex gap-6">
            <div className="flex-1 min-w-0">
              <RoomFeed />
            </div>
            <div className="hidden xl:block w-72 shrink-0">
              <Leaderboard compact />
            </div>
          </div>
        );
      case "dna":
        return <TradingDNA />;
      case "strategy":
        return <StrategyTab />;
      case "moves":
        return <MovesTab />;
      case "leaderboard":
        return <Leaderboard />;
      default:
        return <RoomFeed />;
    }
  };

  return (
    <div className="h-screen flex bg-background overflow-hidden">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 lg:static lg:z-auto
          transform transition-transform duration-200
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
      >
        <Sidebar
          activeTab={activeTab}
          onTabChange={(tab) => {
            setActiveTab(tab);
            setSidebarOpen(false);
          }}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-4 text-text-secondary hover:text-text-primary"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <TopBar />
          </div>
        </div>

        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto">{renderContent()}</div>
        </main>
      </div>
    </div>
  );
}
