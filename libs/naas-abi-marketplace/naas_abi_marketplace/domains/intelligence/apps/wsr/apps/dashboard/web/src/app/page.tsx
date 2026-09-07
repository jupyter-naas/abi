'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { isAuthenticated } from '@/lib/auth';
import LoginPage from '@/components/LoginPage';

const WSR = dynamic(() => import('@/components/WSR'), {
  ssr: false,
  loading: () => (
    <div className="w-screen h-screen bg-black flex items-center justify-center">
      <div className="font-mono text-green-400 text-center space-y-3">
        <div className="text-3xl tracking-widest animate-pulse">◉ WORLD SITUATION ROOM</div>
        <div className="text-xs text-green-500/50 tracking-widest">LOADING GEOSPATIAL ENGINE...</div>
      </div>
    </div>
  ),
});

export default function Page() {
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, []);

  // While checking session (SSR/hydration gap) show nothing to avoid flash
  if (authed === null) return null;

  if (!authed) {
    return <LoginPage onSuccess={() => setAuthed(true)} />;
  }

  return <WSR />;
}
