import './globals.css';
import type { Metadata } from 'next';
import { AuthProvider } from '@/lib/auth-context';

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
    <html lang="en">
      <body className="bg-paper-100 text-ink-900 font-body antialiased min-h-screen">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
