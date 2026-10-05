'use client';
import type { LayerId, DetectionMode } from '@/lib/types';

interface LayerCounts {
  satellites: number;
  flights: number;
  military: number;
  earthquakes: number;
  cctv: number;
}

interface DataLayerPanelProps {
  visibility: Record<LayerId, boolean>;
  onToggle: (layer: LayerId) => void;
  detectionMode: DetectionMode;
  onDetectionChange: (mode: DetectionMode) => void;
  cameraHeight?: number;
  counts?: Partial<LayerCounts>;
}

const LAYERS: { id: LayerId; label: string; color: string; countKey: keyof LayerCounts }[] = [
  { id: 'satellites',  label: 'SATELLITES',   color: 'text-green-400',  countKey: 'satellites'  },
  { id: 'flights',     label: 'CIVIL FLIGHTS', color: 'text-cyan-400',   countKey: 'flights'     },
  { id: 'military',    label: 'MIL FLIGHTS',   color: 'text-orange-400', countKey: 'military'    },
  { id: 'earthquakes', label: 'SEISMIC',        color: 'text-red-400',    countKey: 'earthquakes' },
  { id: 'cctv',        label: 'CCTV CAMERAS',  color: 'text-pink-400',   countKey: 'cctv'        },
];

function zoomLabel(h: number) {
  if (h > 8000000) return 'ORBIT';
  if (h > 2000000) return 'CONTINENTAL';
  if (h > 300000)  return 'REGIONAL';
  if (h > 30000)   return 'CITY';
  if (h > 3000)    return 'DISTRICT';
  return 'STREET';
}

export default function DataLayerPanel({
  visibility, onToggle, detectionMode, onDetectionChange, cameraHeight = 20000000, counts = {},
}: DataLayerPanelProps) {
  return (
    <div className="font-mono text-xs" style={{ background: 'rgba(0,0,0,0.88)', border: '1px solid rgba(0,255,65,0.25)', backdropFilter: 'blur(4px)' }}>
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-green-500/20 flex items-center justify-between">
        <span className="text-green-500/50 tracking-widest text-[10px] uppercase">Object Registry</span>
        <span className="text-[9px] text-green-400/40 tracking-widest">{zoomLabel(cameraHeight)}</span>
      </div>

      {/* Layer toggles with live counts */}
      <div className="p-2 space-y-0.5">
        {LAYERS.map((l) => {
          const count = counts[l.countKey] ?? 0;
          const active = visibility[l.id];
          return (
            <button
              key={l.id}
              onClick={() => onToggle(l.id)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 border transition-all ${
                active
                  ? 'border-green-500/30 bg-green-500/5'
                  : 'border-transparent opacity-40'
              }`}
            >
              {/* Pulse dot */}
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${active ? 'bg-current animate-pulse' : 'bg-green-900'} ${l.color}`} />

              {/* Label */}
              <span className={`text-[11px] flex-1 text-left ${active ? l.color : 'text-green-500/30'}`}>
                {l.label}
              </span>

              {/* Live count badge */}
              <span
                className={`text-[10px] tabular-nums font-bold tracking-tight px-1.5 py-0.5 rounded-sm transition-all ${
                  active && count > 0
                    ? `${l.color} bg-current/10`
                    : 'text-green-500/20'
                }`}
              >
                {active ? count.toLocaleString() : '—'}
              </span>

              {l.id === 'cctv' && active && cameraHeight < 15000000 && (
                <span className="text-[9px] text-pink-400/40 ml-0.5">vis</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Detection mode */}
      <div className="px-3 py-2 border-t border-green-500/15 space-y-1">
        <div className="text-green-500/40 tracking-widest text-[9px] uppercase mb-1">Sat density</div>
        <div className="flex gap-1">
          {(['sparse', 'full'] as DetectionMode[]).map((m) => (
            <button key={m} onClick={() => onDetectionChange(m)}
              className={`flex-1 py-0.5 text-[10px] tracking-wider border transition-all uppercase ${
                detectionMode === m
                  ? 'border-green-400 text-green-300 bg-green-500/10'
                  : 'border-green-500/20 text-green-500/40 hover:border-green-500/40'
              }`}>
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Keyboard hint */}
      <div className="px-3 py-1.5 border-t border-green-500/10">
        <div className="text-green-500/25 text-[9px] leading-4">
          1-5 view mode · Q W E R T landmarks<br />
          SPACE dive · ESC deselect
        </div>
      </div>
    </div>
  );
}
