import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OS-Agent",
  description: "Chat frontend for the agent",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
