'use client';
import type { ShaderMode, ShaderParams } from '@/lib/types';

interface ShaderPanelProps {
  mode: ShaderMode;
  params: ShaderParams;
  onModeChange: (mode: ShaderMode) => void;
  onParamChange: (key: keyof ShaderParams, value: number) => void;
}

const MODES: { id: ShaderMode; label: string; key: string }[] = [
  { id: 'normal',  label: 'NORMAL',  key: '1' },
  { id: 'crt',     label: 'CRT',     key: '2' },
  { id: 'nvg',     label: 'NVG',     key: '3' },
  { id: 'thermal', label: 'THERMAL', key: '4' },
  { id: 'flare',   label: 'FLARE',   key: '5' },
];

export default function ShaderPanel({ mode, params, onModeChange, onParamChange }: ShaderPanelProps) {
  return (
    <div className="font-mono text-xs" style={{ background: 'rgba(0,0,0,0.85)', border: '1px solid rgba(0,255,65,0.25)', backdropFilter: 'blur(4px)' }}>
      <div className="px-3 py-1.5 border-b border-green-500/20">
        <span className="text-green-500/50 tracking-widest text-[10px] uppercase">View Mode</span>
      </div>

      <div className="p-2 grid grid-cols-5 gap-1">
        {MODES.map((m) => (
          <button
            key={m.id}
            onClick={() => onModeChange(m.id)}
            className={`px-1.5 py-1 text-[10px] tracking-wider border transition-all ${
              mode === m.id
                ? 'border-green-400 text-green-300 bg-green-500/15 font-bold'
                : 'border-green-500/20 text-green-500/50 hover:border-green-500/50 hover:text-green-400/70'
            }`}
            title={`Press ${m.key}`}
          >
            [{m.key}] {m.label}
          </button>
        ))}
      </div>

      {mode === 'crt' && (
        <div className="px-3 pb-2 space-y-2 border-t border-green-500/10 pt-2">
          <Slider label="SCANLINES" value={params.scanlineIntensity} min={0} max={1} step={0.05}
            onChange={(v) => onParamChange('scanlineIntensity', v)} />
          <Slider label="PIXELATION" value={params.pixelation} min={1} max={8} step={0.5}
            onChange={(v) => onParamChange('pixelation', v)} />
        </div>
      )}

      {mode === 'nvg' && (
        <div className="px-3 pb-2 space-y-2 border-t border-green-500/10 pt-2">
          <Slider label="SENSITIVITY" value={params.sensitivity} min={0.5} max={5} step={0.1}
            onChange={(v) => onParamChange('sensitivity', v)} />
        </div>
      )}

      {(mode === 'normal' || mode === 'flare') && (
        <div className="px-3 pb-2 space-y-2 border-t border-green-500/10 pt-2">
          <Slider label="BLOOM" value={params.bloomBrightness} min={0} max={1} step={0.05}
            onChange={(v) => onParamChange('bloomBrightness', v)} />
        </div>
      )}
    </div>
  );
}

function Slider({ label, value, min, max, step, onChange }: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between">
        <span className="text-green-500/50">{label}</span>
        <span className="text-green-300 tabular-nums">{value.toFixed(2)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1 appearance-none bg-green-900/40 rounded cursor-pointer accent-green-400"
      />
    </div>
  );
}
