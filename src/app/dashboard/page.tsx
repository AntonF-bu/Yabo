"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { getProfile, saveOnboardingResults, OnboardingResults } from "@/lib/db";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import DiscoverTab from "@/components/dashboard/DiscoverTab";
import RoomTab from "@/components/dashboard/RoomTab";
import PredictTab from "@/components/dashboard/PredictTab";
import BoardTab from "@/components/dashboard/BoardTab";
import MirrorTab from "@/components/dashboard/MirrorTab";
import StrategyTab from "@/components/dashboard/StrategyTab";
import MovesTab from "@/components/dashboard/MovesTab";
import {
  Compass,
  MessageSquare,
  Target,
  BarChart3,
  ScanEye,
  Lightbulb,
  Zap,
  Menu,
} from "lucide-react";

const mobileTabs = [
  { id: "discover", icon: Compass },
  { id: "room", icon: MessageSquare },
  { id: "predict", icon: Target },
  { id: "board", icon: BarChart3 },
  { id: "mirror", icon: ScanEye },
  { id: "strategy", icon: Lightbulb },
  { id: "moves", icon: Zap },
];

export default function DashboardPage() {
  const { user, isSignedIn } = useUser();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("discover");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function checkOnboarding() {
      if (!isSignedIn || !user) {
        setReady(true);
        return;
      }

      // Check for pending localStorage results from pre-signup quiz
      const pending = localStorage.getItem("yabo_onboarding");
      if (pending) {
        try {
          const results: OnboardingResults = JSON.parse(pending);
          await saveOnboardingResults(user.id, results);
          localStorage.removeItem("yabo_onboarding");
        } catch {
          // Supabase may not be set up -- continue to dashboard
        }
        setReady(true);
        return;
      }

      // Check if user has completed onboarding
      try {
        const profile = await getProfile(user.id);
        if (!profile || !profile.onboarding_complete) {
          router.push("/onboarding");
          return;
        }
      } catch {
        // Supabase not available -- let user through
      }
      setReady(true);
    }
    checkOnboarding();
  }, [isSignedIn, user, router]);

  if (!ready) {
    return (
      <div className="h-screen bg-bg flex items-center justify-center">
        <div className="w-3 h-3 rounded-full bg-teal animate-pulse-dot" />
      </div>
    );
  }

  const renderContent = () => {
    switch (activeTab) {
      case "discover":
        return <DiscoverTab />;
      case "room":
        return <RoomTab />;
      case "predict":
        return <PredictTab />;
      case "board":
        return <BoardTab />;
      case "mirror":
        return <MirrorTab />;
      case "strategy":
        return <StrategyTab />;
      case "moves":
        return <MovesTab />;
      default:
        return <DiscoverTab />;
    }
  };

  return (
    <div className="h-screen flex bg-bg overflow-hidden">
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div
        className={`
          fixed inset-y-0 left-0 z-50 md:static md:z-auto
          transform transition-transform duration-200
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
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

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center">
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden p-4 text-text-sec hover:text-text"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <TopBar />
          </div>
        </div>

        <main className="flex-1 overflow-y-auto p-6 pb-20 md:pb-6">
          <div className="max-w-4xl mx-auto">{renderContent()}</div>
        </main>
      </div>

      <div className="fixed bottom-0 left-0 right-0 md:hidden bg-bg border-t border-border z-40">
        <div className="flex items-center justify-around py-2">
          {mobileTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`p-2 rounded-lg transition-colors ${
                  isActive ? "text-teal" : "text-text-ter"
                }`}
              >
                <Icon className="w-5 h-5" />
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
