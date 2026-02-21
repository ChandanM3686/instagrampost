import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SPKR — Speak Your Mind. We Post It.",
  description: "Submit your content anonymously and we'll post it to Instagram. Free and promotional posts available.",
  keywords: "anonymous posting, instagram, community, speak, SPKR",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
