"use client";

import { useState, useCallback, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { saveOnboardingResults, OnboardingResults } from "@/lib/db";
import QuizSplash from "@/components/onboarding/QuizSplash";
import TraderTypeStep from "@/components/onboarding/TraderTypeStep";
import SectorStep from "@/components/onboarding/SectorStep";
import ScenarioStep from "@/components/onboarding/ScenarioStep";
import RiskStep from "@/components/onboarding/RiskStep";
import ExperienceStep from "@/components/onboarding/ExperienceStep";
import ProfileReveal from "@/components/onboarding/ProfileReveal";
import ProgressBar from "@/components/onboarding/ProgressBar";
import GuidePanel from "@/components/guide/GuidePanel";

type Step = "splash" | "trader-type" | "sectors" | "scenario" | "risk" | "experience" | "reveal";

const QUESTION_STEPS: Step[] = ["trader-type", "sectors", "scenario", "risk", "experience"];

export default function OnboardingPage() {
  const { user, isSignedIn } = useUser();
  const router = useRouter();

  const [guideActive, setGuideActive] = useState(false);
  useEffect(() => {
    setGuideActive(localStorage.getItem("yabo_guide") === "true");
  }, []);

  const [step, setStep] = useState<Step>("splash");
  const [direction, setDirection] = useState<"forward" | "back">("forward");
  const [animating, setAnimating] = useState(false);
  const [saving, setSaving] = useState(false);

  // Quiz state
  const [traderType, setTraderType] = useState("");
  const [sectors, setSectors] = useState<string[]>([]);
  const [scenario, setScenario] = useState("");
  const [risk, setRisk] = useState("");
  const [experience, setExperience] = useState("");

  const goTo = useCallback((next: Step) => {
    setDirection("forward");
    setAnimating(true);
    setTimeout(() => {
      setStep(next);
      setAnimating(false);
    }, 300);
  }, []);

  // Auto-advance handler for single-select steps
  const autoAdvance = useCallback(
    (next: Step, delay = 400) => {
      setTimeout(() => goTo(next), delay);
    },
    [goTo],
  );

  const handleComplete = useCallback(async () => {
    const results: OnboardingResults = {
      traderType,
      sectors,
      riskTolerance: risk,
      experienceLevel: experience,
      scenarioChoice: scenario,
    };

    setSaving(true);

    if (isSignedIn && user) {
      try {
        await saveOnboardingResults(user.id, results);
      } catch {
        // Supabase may not be set up yet -- save locally as fallback
        localStorage.setItem("yabo_onboarding", JSON.stringify(results));
      }
      router.push("/dashboard");
    } else {
      // Save to localStorage for post-signup retrieval
      localStorage.setItem("yabo_onboarding", JSON.stringify(results));
      router.push("/sign-up");
    }
  }, [traderType, sectors, risk, experience, scenario, isSignedIn, user, router]);

  // Progress calculation
  const questionIndex = QUESTION_STEPS.indexOf(step);
  const showProgress = questionIndex >= 0;

  // Step transition classes
  const stepClass = animating
    ? "opacity-0 translate-x-10 transition-all duration-300 ease-out"
    : "opacity-100 translate-x-0 transition-all duration-400 ease-[cubic-bezier(0.16,1,0.3,1)]";

  return (
    <div className="min-h-screen bg-bg">
      {guideActive && (
        <div className="max-w-md mx-auto px-6 mb-4">
          <GuidePanel section="onboarding" />
        </div>
      )}
      {/* Progress bar -- only during questions */}
      {showProgress && (
        <ProgressBar current={questionIndex + 1} total={QUESTION_STEPS.length} />
      )}

      {/* Step content */}
      <div className={step === "splash" || step === "reveal" ? "" : `pt-12 pb-12 ${stepClass}`}>
        {step === "splash" && (
          <QuizSplash onBegin={() => goTo("trader-type")} />
        )}

        {step === "trader-type" && (
          <TraderTypeStep
            value={traderType}
            onChange={(val) => {
              setTraderType(val);
              autoAdvance("sectors");
            }}
          />
        )}

        {step === "sectors" && (
          <SectorStep
            value={sectors}
            onChange={setSectors}
            onContinue={() => goTo("scenario")}
          />
        )}

        {step === "scenario" && (
          <ScenarioStep
            value={scenario}
            onChange={(val) => {
              setScenario(val);
              autoAdvance("risk");
            }}
          />
        )}

        {step === "risk" && (
          <RiskStep
            value={risk}
            onChange={(val) => {
              setRisk(val);
              autoAdvance("experience");
            }}
          />
        )}

        {step === "experience" && (
          <ExperienceStep
            value={experience}
            onChange={(val) => {
              setExperience(val);
              autoAdvance("reveal");
            }}
          />
        )}

        {step === "reveal" && (
          <ProfileReveal
            results={{
              traderType,
              sectors,
              riskTolerance: risk,
              experienceLevel: experience,
              scenarioChoice: scenario,
            }}
            onComplete={handleComplete}
            saving={saving}
          />
        )}
      </div>
    </div>
  );
}
