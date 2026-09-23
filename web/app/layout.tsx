import "./globals.css";
import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Space_Grotesk } from "next/font/google";
import { AuthProvider } from "@/lib/auth-context";

/**
 * The design system names three typefaces. They were referenced through CSS
 * variables that nothing ever defined with real font files, so every screen
 * fell back to the platform default. `next/font` self-hosts them and sets the
 * variables the Tailwind config already reads.
 */
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MetrologyAI — Enforcement & Compliance Dashboard",
  description:
    "Automated Compliance Engine for Legal Metrology (Packaged Commodities) Rules, 2011",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${spaceGrotesk.variable} ${ibmPlexMono.variable}`}
    >
      <body className="min-h-screen bg-paper-100 font-body text-ink-900 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
