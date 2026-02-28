'use client';
import type { ShaderMode, LayerId } from '@/lib/types';

interface StatusBarProps {
  shaderMode: ShaderMode;
  satCount: number;
  flightCount: number;
  militaryCount: number;
  quakeCount: number;
  layerVisibility: Record<LayerId, boolean>;
  cityName: string;
}

const MODE_LABELS: Record<ShaderMode, string> = {
  normal: 'NORMAL',
  crt: 'CRT-MODE',
  nvg: 'NVG',
  thermal: 'THERMAL',
  flare: 'FLARE',
};

export default function StatusBar({ shaderMode, satCount, flightCount, militaryCount, quakeCount, cityName }: StatusBarProps) {
  const now = new Date();
  const utc = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';

  return (
    <div className="absolute top-0 left-0 right-0 h-8 flex items-center justify-between px-4 text-xs font-mono z-20 border-b border-green-500/30"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}>
      <div className="flex items-center gap-4">
        <span className="text-green-400 font-bold tracking-widest">◉ WORLDVIEW</span>
        <span className="text-green-500/60">|</span>
        <span className="text-green-300/80 uppercase tracking-wider">{cityName}</span>
      </div>

      <div className="flex items-center gap-5 text-green-400/70">
        <Stat label="SAT" value={satCount} />
        <Stat label="FLT" value={flightCount} />
        <Stat label="MIL" value={militaryCount} color="text-orange-400/80" />
        <Stat label="SES" value={quakeCount} color="text-red-400/80" />
      </div>

      <div className="flex items-center gap-4">
        <span
          className={`px-2 py-0.5 text-[10px] font-bold tracking-widest border ${
            shaderMode === 'normal'
              ? 'border-green-500/40 text-green-400/60'
              : 'border-green-400 text-green-300 bg-green-500/10'
          }`}
        >
          {MODE_LABELS[shaderMode]}
        </span>
        <span className="text-green-500/50">{utc}</span>
      </div>
    </div>
  );
}

function Stat({ label, value, color = 'text-green-400' }: { label: string; value: number; color?: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="text-green-500/50">{label}</span>
      <span className={`font-bold tabular-nums ${color}`}>{value.toLocaleString()}</span>
    </span>
  );
}
