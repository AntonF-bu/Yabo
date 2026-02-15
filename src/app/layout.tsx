import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
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
        variables: {
          colorPrimary: "#1A1715",
          colorBackground: "#FAF8F4",
          colorText: "#1A1715",
          colorTextSecondary: "#8A8580",
          colorInputBackground: "#F3F0EA",
          colorInputText: "#1A1715",
          borderRadius: "10px",
        },
        elements: {
          card: {
            backgroundColor: "#FAF8F4",
            border: "1px solid #EDE9E3",
            boxShadow: "0 8px 32px rgba(26,23,21,0.08)",
          },
          formButtonPrimary: {
            backgroundColor: "#1A1715",
            color: "#FAF8F4",
            fontWeight: "600",
            fontFamily: "Inter, system-ui, sans-serif",
          },
          footerActionLink: {
            color: "#9A7B5B",
          },
          headerTitle: {
            color: "#1A1715",
            fontFamily: "Newsreader, Georgia, serif",
          },
          headerSubtitle: {
            color: "#8A8580",
          },
          socialButtonsBlockButton: {
            backgroundColor: "#F3F0EA",
            border: "1px solid #EDE9E3",
            color: "#1A1715",
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
            href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,500&family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
            rel="stylesheet"
          />
        </head>
        <body className="font-body">{children}</body>
      </html>
    </ClerkProvider>
  );
}
