'use client';
import type { ShaderMode, LayerId } from '@/lib/types';
import GeoSearch, { type GeoResult } from './GeoSearch';

interface StatusBarProps {
  shaderMode: ShaderMode;
  layerVisibility: Record<LayerId, boolean>;
  onSelect: (result: GeoResult) => void;
}

const MODE_LABELS: Record<ShaderMode, string> = {
  normal:  'NORMAL',
  crt:     'CRT-MODE',
  nvg:     'NVG',
  thermal: 'THERMAL',
  flare:   'FLARE',
};

export default function StatusBar({ shaderMode, onSelect }: StatusBarProps) {
  const now = new Date();
  const utc = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';

  return (
    /**
     * 3-column CSS grid navbar — the only reliable way to get a truly centered
     * middle column while keeping left and right flush to their edges.
     * z-30 so the search dropdown stacking context beats the ticker at z-20.
     */
    <div
      className="absolute top-0 left-0 right-0 h-9 z-30 grid grid-cols-3 items-center border-b border-green-500/30"
      style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(6px)' }}
    >
      {/* Col 1 — logo, left-aligned */}
      <div className="flex items-center px-4">
        <span className="text-green-400 font-bold tracking-widest font-mono text-xs">◉ WSR</span>
      </div>

      {/* Col 2 — search, centered within its column */}
      <div className="flex items-center justify-center h-full">
        <GeoSearch onSelect={onSelect} compact />
      </div>

      {/* Col 3 — shader mode + clock, right-aligned */}
      <div className="flex items-center justify-end gap-4 px-4 font-mono text-xs">
        <span
          className={`px-2 py-0.5 text-[10px] font-bold tracking-widest border ${
            shaderMode === 'normal'
              ? 'border-green-500/30 text-green-400/50'
              : 'border-green-400 text-green-300 bg-green-500/10'
          }`}
        >
          {MODE_LABELS[shaderMode]}
        </span>
        <span className="text-green-500/40 tabular-nums">{utc}</span>
      </div>
    </div>
  );
}
