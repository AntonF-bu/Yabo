export default function OnboardingPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#161B26",
        display: "flex",
        flexDirection: "column" as const,
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        fontFamily: "'Plus Jakarta Sans', sans-serif",
      }}
    >
      <h1
        style={{
          fontFamily: "'Fraunces', serif",
          fontStyle: "italic",
          fontSize: 36,
          fontWeight: 400,
          color: "#E8E4DC",
          marginBottom: 12,
        }}
      >
        Welcome to Yabo
      </h1>
      <p
        style={{
          color: "rgba(232,228,220,0.45)",
          fontSize: 16,
          marginBottom: 32,
        }}
      >
        Your onboarding experience is coming soon.
      </p>
      <a href="/dashboard">
        <button
          style={{
            padding: "14px 36px",
            borderRadius: 8,
            border: "none",
            background: "#00BFA6",
            color: "#161B26",
            fontWeight: 700,
            fontSize: 15,
            cursor: "pointer",
            fontFamily: "'Plus Jakarta Sans', sans-serif",
          }}
        >
          Go to Dashboard
        </button>
      </a>
    </div>
  );
}
