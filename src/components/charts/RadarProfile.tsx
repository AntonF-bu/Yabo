"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import { behavioralTraits } from "@/lib/mock-data";
import { BehavioralTrait } from "@/types";

interface RadarProfileProps {
  traits?: BehavioralTrait[];
}

export default function RadarProfile({ traits }: RadarProfileProps) {
  const source = traits || behavioralTraits;
  const data = source.map((t) => ({
    trait: t.name,
    value: t.score,
    fullMark: 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
        <PolarGrid stroke="#EDE9E3" />
        <PolarAngleAxis
          dataKey="trait"
          tick={{ fontSize: 10, fill: "#A09A94" }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 100]}
          tick={false}
          axisLine={false}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke="#9A7B5B"
          fill="#9A7B5B"
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
