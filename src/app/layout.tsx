import type { Metadata } from "next";
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
  );
}
