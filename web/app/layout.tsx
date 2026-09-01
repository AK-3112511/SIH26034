import './globals.css';
import type { Metadata } from 'next';
import { Space_Grotesk, Inter, IBM_Plex_Mono } from 'next/font/google';

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  weight: ['500', '700'],
  variable: '--font-space-grotesk',
  display: 'swap',
});

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-inter',
  display: 'swap',
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['500'],
  variable: '--font-ibm-plex-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'MetrologyAI — Enforcement & Compliance Dashboard',
  description: 'Automated Compliance Engine for Legal Metrology (Packaged Commodities) Rules, 2011',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${inter.variable} ${ibmPlexMono.variable}`}>
      <body className="bg-paper-100 text-ink-900 font-body antialiased min-h-screen">
        <header className="bg-ink-900 text-white px-6 py-4 shadow-sm border-b border-brass-500/20">
          <div className="max-w-desktop mx-auto flex justify-between items-center">
            <h1 className="font-display text-xl font-semibold tracking-tight text-white">
              MetrologyAI Dashboard
            </h1>
            <span className="font-body text-xs font-medium text-brass-500 tracking-wide uppercase">
              Legal Metrology Division — Enforcement Portal
            </span>
          </div>
        </header>
        <main className="max-w-desktop mx-auto px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
