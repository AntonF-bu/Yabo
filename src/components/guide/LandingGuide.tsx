"use client";

import { useState, useEffect } from "react";
import GuidePanel from "@/components/guide/GuidePanel";

export default function LandingGuide() {
  const [active, setActive] = useState(false);
  useEffect(() => {
    setActive(localStorage.getItem("yabo_guide") === "true");
  }, []);

  if (!active) return null;

  return (
    <div className="max-w-3xl mx-auto px-6 pt-4">
      <GuidePanel section="landing" />
    </div>
  );
}
