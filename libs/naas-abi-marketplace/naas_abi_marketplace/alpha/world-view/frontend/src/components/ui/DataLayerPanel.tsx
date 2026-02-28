'use client';
import type { LayerId, DetectionMode } from '@/lib/types';

interface DataLayerPanelProps {
  visibility: Record<LayerId, boolean>;
  onToggle: (layer: LayerId) => void;
  detectionMode: DetectionMode;
  onDetectionChange: (mode: DetectionMode) => void;
  cameraHeight?: number;
}

const LAYERS: { id: LayerId; label: string; color: string }[] = [
  { id: 'satellites',  label: 'SATELLITES',    color: 'text-green-400' },
  { id: 'flights',     label: 'CIVIL FLIGHTS',  color: 'text-cyan-400' },
  { id: 'military',    label: 'MIL FLIGHTS',    color: 'text-orange-400' },
  { id: 'earthquakes', label: 'SEISMIC',         color: 'text-red-400' },
  { id: 'cctv',        label: 'CCTV CAMERAS',   color: 'text-pink-400' },
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
  visibility, onToggle, detectionMode, onDetectionChange, cameraHeight = 20000000,
}: DataLayerPanelProps) {
  return (
    <div className="font-mono text-xs" style={{ background: 'rgba(0,0,0,0.88)', border: '1px solid rgba(0,255,65,0.25)', backdropFilter: 'blur(4px)' }}>
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-green-500/20 flex items-center justify-between">
        <span className="text-green-500/50 tracking-widest text-[10px] uppercase">Data Layers</span>
        <span className="text-[9px] text-green-400/40 tracking-widest">{zoomLabel(cameraHeight)}</span>
      </div>

      {/* Layer toggles */}
      <div className="p-2 space-y-0.5">
        {LAYERS.map((l) => (
          <button
            key={l.id}
            onClick={() => onToggle(l.id)}
            className={`w-full flex items-center gap-2 px-2 py-1 border transition-all ${
              visibility[l.id]
                ? 'border-green-500/30 bg-green-500/5'
                : 'border-transparent opacity-40'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${visibility[l.id] ? 'bg-current animate-pulse' : 'bg-green-900'} ${l.color}`} />
            <span className={`text-[11px] ${visibility[l.id] ? l.color : 'text-green-500/30'}`}>{l.label}</span>
            {l.id === 'cctv' && visibility[l.id] && cameraHeight < 15000000 && (
              <span className="ml-auto text-[9px] text-pink-400/40">visible</span>
            )}
          </button>
        ))}
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
          1-5 view mode<br />
          Q W E R T landmarks<br />
          ESC deselect
        </div>
      </div>
    </div>
  );
}
