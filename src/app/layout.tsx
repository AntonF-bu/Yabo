import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import "./globals.css";

export const metadata: Metadata = {
  title: "Yabo - The Proving Ground",
  description:
    "Prove your skill. Earn your seat. Manage real capital. America's Got Talent for Stock Trading.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider
      appearance={{
        baseTheme: dark,
        variables: {
          colorPrimary: "#00BFA6",
          colorBackground: "#1E2432",
          colorText: "#E8E4DC",
          colorTextSecondary: "rgba(232,228,220,0.45)",
          colorInputBackground: "#252B3B",
          colorInputText: "#E8E4DC",
          borderRadius: "8px",
        },
        elements: {
          card: {
            backgroundColor: "#1E2432",
            border: "1px solid rgba(232,228,220,0.06)",
            boxShadow: "0 16px 48px rgba(0,0,0,0.3)",
          },
          formButtonPrimary: {
            backgroundColor: "#00BFA6",
            color: "#161B26",
            fontWeight: "700",
          },
          footerActionLink: {
            color: "#00BFA6",
          },
          headerTitle: {
            color: "#E8E4DC",
          },
          headerSubtitle: {
            color: "rgba(232,228,220,0.45)",
          },
          socialButtonsBlockButton: {
            backgroundColor: "#252B3B",
            border: "1px solid rgba(232,228,220,0.06)",
            color: "#E8E4DC",
          },
        },
      }}
    >
      <html lang="en">
        <head>
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link
            rel="preconnect"
            href="https://fonts.gstatic.com"
            crossOrigin="anonymous"
          />
          <link
            href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fraunces:ital,opsz,wght@1,9..144,400&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
            rel="stylesheet"
          />
        </head>
        <body className="font-body">{children}</body>
      </html>
    </ClerkProvider>
  );
}
