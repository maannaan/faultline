import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Faultline",
  description: "Memory timeline for agent assertions, sources, and conflicts.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Sora:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <nav className="mx-auto flex max-w-6xl gap-4 px-4 pt-4 text-sm lg:px-6">
          <a href="/" className="font-medium">
            Timeline
          </a>
          <a href="/replay" className="font-medium">
            Replay Lab
          </a>
          <a href="/handoff" className="font-medium">
            Handoff
          </a>
          <a href="/bench" className="font-medium">
            Bench
          </a>
        </nav>
        {children}
      </body>
    </html>
  );
}
