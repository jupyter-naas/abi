import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'WORLDVIEW // Geospatial Intelligence',
  description: 'Real-time orbital, flight, and seismic intelligence dashboard',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-black overflow-hidden">{children}</body>
    </html>
  );
}
