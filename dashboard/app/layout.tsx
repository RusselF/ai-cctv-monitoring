import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI CCTV Monitoring",
  description: "Dashboard monitoring hasil deteksi, tracking, dan event zona",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}