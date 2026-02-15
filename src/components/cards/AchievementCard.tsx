import { Achievement } from "@/types";
import {
  Target,
  FileText,
  TrendingUp,
  Award,
  Diamond,
  MessageCircle,
  Crosshair,
  DollarSign,
  Star,
  Lock,
  Check,
} from "lucide-react";

const iconMap: Record<string, React.ElementType> = {
  target: Target,
  "file-text": FileText,
  "trending-up": TrendingUp,
  award: Award,
  gem: Diamond,
  "message-circle": MessageCircle,
  crosshair: Crosshair,
  "dollar-sign": DollarSign,
  star: Star,
};

interface AchievementCardProps {
  achievement: Achievement;
}

export default function AchievementCard({ achievement }: AchievementCardProps) {
  const Icon = iconMap[achievement.icon] || Target;
  const isLocked = achievement.locked;
  const isDone = achievement.done;
  const hasProgress = !isDone && !isLocked && achievement.progress !== undefined && achievement.total !== undefined;
  const progressPct = hasProgress
    ? Math.round(((achievement.progress ?? 0) / (achievement.total ?? 1)) * 100)
    : 0;

  return (
    <div
      className={`p-3.5 rounded-xl border transition-all duration-200 ${
        isDone
          ? "border-green/20 bg-green-light"
          : isLocked
            ? "border-border bg-bg opacity-50"
            : "border-border bg-surface"
      }`}
    >
      <div className="flex items-center gap-2.5 mb-2">
        <div
          className={`w-7 h-7 rounded-lg flex items-center justify-center ${
            isDone
              ? "bg-green/10"
              : isLocked
                ? "bg-surface-hover"
                : "bg-teal-light"
          }`}
        >
          {isLocked ? (
            <Lock className="w-3.5 h-3.5 text-text-ter" />
          ) : isDone ? (
            <Check className="w-3.5 h-3.5 text-green" />
          ) : (
            <Icon className="w-3.5 h-3.5 text-teal" />
          )}
        </div>
        <span
          className={`text-xs font-semibold font-body ${isDone ? "text-green" : isLocked ? "text-text-ter" : "text-text"}`}
        >
          {achievement.name}
        </span>
      </div>
      <p className="text-xs text-text-ter mb-2.5 font-body">{achievement.desc}</p>
      {isDone ? (
        <div className="h-1.5 rounded-full bg-green/20 overflow-hidden">
          <div className="h-full w-full rounded-full bg-green" />
        </div>
      ) : hasProgress ? (
        <div className="space-y-1">
          <div className="h-1.5 rounded-full bg-text-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-teal animate-bar-fill"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <span className="text-[10px] font-mono text-text-ter">
            {achievement.progress}/{achievement.total}
          </span>
        </div>
      ) : (
        <div className="h-1.5 rounded-full bg-text-muted overflow-hidden">
          <div className="h-full w-0 rounded-full bg-surface-hover" />
        </div>
      )}
    </div>
  );
}
