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
        <PolarGrid stroke="rgba(232,228,220,0.06)" />
        <PolarAngleAxis
          dataKey="trait"
          tick={{ fontSize: 10, fill: "rgba(232,228,220,0.45)" }}
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
          stroke="#00BFA6"
          fill="#00BFA6"
          fillOpacity={0.2}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
