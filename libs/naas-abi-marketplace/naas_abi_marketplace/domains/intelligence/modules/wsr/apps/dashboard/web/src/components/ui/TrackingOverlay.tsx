'use client';
import type { TrackedEntity } from '@/lib/types';

interface TrackingOverlayProps {
  entity: TrackedEntity | null;
  onClose: () => void;
}

export default function TrackingOverlay({ entity, onClose }: TrackingOverlayProps) {
  if (!entity) return null;

  const typeColor = entity.type === 'flight'
    ? entity.extra?.isMilitary ? 'text-orange-400' : 'text-cyan-400'
    : entity.type === 'earthquake'
    ? 'text-red-400'
    : 'text-green-400';

  return (
    <div className="absolute top-12 right-4 w-64 z-20 font-mono text-xs"
      style={{ background: 'rgba(0,0,0,0.85)', border: '1px solid rgba(0,255,65,0.3)', backdropFilter: 'blur(4px)' }}>

      <div className="flex items-center justify-between px-3 py-1.5 border-b border-green-500/20">
        <span className="text-green-500/50 tracking-widest uppercase text-[10px]">
          {entity.type === 'satellite' ? '◉ TRACKING SAT' : entity.type === 'flight' ? '✈ TRACKING FLT' : '⚠ SEISMIC EVENT'}
        </span>
        <button onClick={onClose} className="text-green-500/40 hover:text-green-300 transition-colors">✕</button>
      </div>

      <div className="px-3 py-2 space-y-1">
        <div className={`font-bold text-sm tracking-wider ${typeColor}`}>{entity.name}</div>
        <div className="text-green-500/50 text-[10px]">{entity.id}</div>
      </div>

      <div className="px-3 pb-2 space-y-0.5 border-t border-green-500/10 pt-2">
        {entity.lat != null && (
          <Row label="LAT" value={`${entity.lat.toFixed(4)}°`} />
        )}
        {entity.lon != null && (
          <Row label="LON" value={`${entity.lon.toFixed(4)}°`} />
        )}
        {entity.altitude != null && entity.altitude > 0 && (
          <Row label="ALT" value={`${Math.round(entity.altitude / 1000).toLocaleString()} km`} />
        )}
        {entity.velocity != null && entity.velocity > 0 && (
          <Row label="VEL" value={`${Math.round(entity.velocity * 3.6).toLocaleString()} km/h`} />
        )}
        {entity.heading != null && (
          <Row label="HDG" value={`${Math.round(entity.heading)}°`} />
        )}
        {entity.extra && Object.entries(entity.extra).map(([k, v]) => (
          k !== 'isMilitary' && <Row key={k} label={k.toUpperCase()} value={String(v)} />
        ))}
      </div>

      <div className="px-3 py-1.5 border-t border-green-500/10">
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-green-500/50 text-[10px] tracking-widest">LIVE TRACKING</span>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-green-500/40">{label}</span>
      <span className="text-green-300 tabular-nums">{value}</span>
    </div>
  );
}
