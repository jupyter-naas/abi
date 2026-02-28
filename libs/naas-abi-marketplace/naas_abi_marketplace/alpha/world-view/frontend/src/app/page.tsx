'use client';

import dynamic from 'next/dynamic';

const WorldView = dynamic(() => import('@/components/WorldView'), {
  ssr: false,
  loading: () => (
    <div className="w-screen h-screen bg-black flex items-center justify-center">
      <div className="font-mono text-green-400 text-center space-y-3">
        <div className="text-3xl tracking-widest animate-pulse">◉ WORLDVIEW</div>
        <div className="text-xs text-green-500/50 tracking-widest">LOADING GEOSPATIAL ENGINE...</div>
      </div>
    </div>
  ),
});

export default function Page() {
  return <WorldView />;
}
