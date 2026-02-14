export interface Trader {
  id: number;
  name: string;
  dna: string;
  winRate: number;
  sharpe: number;
  rep: number;
  rank: number;
  initials: string;
  streak: number;
  level: number;
  xp: number;
  tier: "Rookie" | "Contender" | "All-Star" | "Fund-Ready" | "Elite";
}

export interface Thesis {
  id: number;
  trader: Trader;
  ticker: string;
  direction: "long" | "short";
  price: number;
  target: number;
  stop: number;
  conviction: number;
  signal: number;
  tqs: number;
  text: string;
  timeAgo: string;
  replies: number;
  repCount: number;
  chartData: number[];
  yesVotes: number;
  noVotes: number;
  expiresIn: string;
  probability: number;
}

export interface Prediction {
  id: number;
  question: string;
  yesProb: number;
  volume: number;
  category: string;
  hot: boolean;
}

export interface StrategyRecommendation {
  ticker: string;
  action: string;
  urgency: "high" | "medium" | "low";
  narrative: string;
  behavioral: string;
  impact: number;
}

export interface BehavioralTrait {
  name: string;
  score: number;
  percentile: number;
  trend: "up" | "down" | "flat";
}

export interface CollectiveMove {
  id: number;
  ticker: string;
  direction: "long" | "short";
  signal: number;
  catalyst: string;
  conviction: number;
  participants: number;
  target: number;
  currentPrice: number;
}

export interface TrendingTicker {
  ticker: string;
  change: number;
  signal: number;
  theses: number;
  hot: boolean;
}

export interface Achievement {
  id: number;
  name: string;
  desc: string;
  icon: string;
  done: boolean;
  progress?: number;
  total?: number;
  locked?: boolean;
}

export interface DailyChallengeData {
  title: string;
  description: string;
  progress: number;
  total: number;
  xpReward: number;
}

export interface UserProfile {
  name: string;
  initials: string;
  archetype: string;
  tier: string;
  level: number;
  xp: number;
  xpToNext: number;
  streak: number;
  portfolioValue: number;
  startingValue: number;
  pnl: number;
  pnlPercent: number;
  winRate: number;
  sharpe: number;
  rep: number;
  positions: number;
  effectiveBets: number;
}
