'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  Bot,
  Captions,
  CaptionsOff,
  Loader2,
  Mic,
  MicOff,
  PhoneOff,
  Settings2,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getLogoUrl } from '@/lib/logo-url';
import {
  CALL_LANGUAGES,
  CALL_VOICES,
  type CallLanguageSetting,
  type CallSettings,
} from './voice-call-engine';

export type VoiceCallState =
  | 'listening'
  | 'user_speaking'
  | 'unfinished_hold'
  | 'transcribing'
  | 'thinking'
  | 'speaking';

export interface VoiceCallBarProps {
  agentName: string;
  agentLogoUrl?: string | null;
  callState: VoiceCallState;
  muted: boolean;
  seconds: number;
  analyser: AnalyserNode | null;
  outputAnalyser?: AnalyserNode | null;
  partialTranscript?: string;
  lastUserTranscript?: string;
  currentAgentSentence?: string;
  activeToolLabel?: string | null;
  settings: CallSettings;
  onChangeSettings: (next: Partial<CallSettings>) => void;
  onToggleMute: () => void;
  onEndCall: () => void;
}

function readAnalyserRms(analyser: AnalyserNode, buf: Uint8Array<ArrayBuffer>): number {
  analyser.getByteTimeDomainData(buf);
  let sumSq = 0;
  for (let i = 0; i < buf.length; i++) {
    const v = (buf[i] - 128) / 128;
    sumSq += v * v;
  }
  return Math.sqrt(sumSq / buf.length);
}

function readAnalyserBands(
  analyser: AnalyserNode,
  freqBuf: Uint8Array<ArrayBuffer>,
): { low: number; mid: number; high: number } {
  analyser.getByteFrequencyData(freqBuf);
  const len = freqBuf.length;
  if (len === 0) return { low: 0, mid: 0, high: 0 };

  const lowEnd = Math.max(2, Math.floor(len * 0.12));
  const midEnd = Math.max(lowEnd + 2, Math.floor(len * 0.42));
  const highEnd = Math.max(midEnd + 2, Math.floor(len * 0.78));

  let lowSum = 0;
  for (let i = 1; i < lowEnd; i++) lowSum += freqBuf[i] / 255;
  let midSum = 0;
  for (let i = lowEnd; i < midEnd; i++) midSum += freqBuf[i] / 255;
  let highSum = 0;
  for (let i = midEnd; i < highEnd; i++) highSum += freqBuf[i] / 255;

  return {
    low: lowSum / Math.max(1, lowEnd - 1),
    mid: midSum / Math.max(1, midEnd - lowEnd),
    high: highSum / Math.max(1, highEnd - midEnd),
  };
}

function fitCanvas(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

const WAVE_BARS = 44;
const WAVE_SAMPLE_MS = 45;

function formatDuration(total: number) {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function VoiceCallBar({
  agentName,
  agentLogoUrl,
  callState,
  muted,
  seconds,
  analyser,
  outputAnalyser,
  partialTranscript,
  lastUserTranscript,
  currentAgentSentence,
  activeToolLabel,
  settings,
  onChangeSettings,
  onToggleMute,
  onEndCall,
}: VoiceCallBarProps) {
  const [captionsEnabled, setCaptionsEnabled] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [inputDevices, setInputDevices] = useState<MediaDeviceInfo[]>([]);

  const orbCanvasRef = useRef<HTMLCanvasElement>(null);
  const waveCanvasRef = useRef<HTMLCanvasElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  const smoothedLevelRef = useRef(0);
  const phaseRef = useRef(0);

  const resolvedLogoUrl = agentLogoUrl ? getLogoUrl(agentLogoUrl) : undefined;
  const isWorking = callState === 'thinking' || callState === 'transcribing';

  // Harmonic ring orb around the agent logo: mic while listening, ABI's output while speaking.
  useEffect(() => {
    const canvas = orbCanvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    let rafId = 0;
    const inTimeBuf = new Uint8Array(new ArrayBuffer(analyser?.fftSize ?? 512));
    const inFreqBuf = new Uint8Array(new ArrayBuffer(analyser?.frequencyBinCount ?? 256));
    const outTimeBuf = new Uint8Array(new ArrayBuffer(outputAnalyser?.fftSize ?? 512));
    const outFreqBuf = new Uint8Array(new ArrayBuffer(outputAnalyser?.frequencyBinCount ?? 256));

    const resize = () => fitCanvas(canvas, ctx);
    resize();
    window.addEventListener('resize', resize);

    const drawOrb = (now: number) => {
      rafId = requestAnimationFrame(drawOrb);

      const width = canvas.clientWidth || 124;
      const height = canvas.clientHeight || 124;
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      const baseRadius = Math.min(width, height) * 0.255;
      // Ring amplitudes were tuned on a 148px orb.
      const scale = Math.min(width, height) / 148;

      let targetLevel = 0;
      let bands = { low: 0, mid: 0, high: 0 };

      if (callState === 'speaking') {
        if (outputAnalyser) {
          const rms = readAnalyserRms(outputAnalyser, outTimeBuf);
          bands = readAnalyserBands(outputAnalyser, outFreqBuf);
          targetLevel = Math.min(1, rms * 4.2 + bands.mid * 0.45);
        }
        if (targetLevel < 0.08) {
          const t = now / 130;
          targetLevel =
            0.22 + 0.18 * Math.abs(Math.sin(t)) + 0.12 * Math.abs(Math.cos(t * 1.9));
          bands = {
            low: 0.35 + 0.2 * Math.sin(t * 0.9),
            mid: 0.4 + 0.25 * Math.cos(t * 1.5),
            high: 0.25 + 0.15 * Math.sin(t * 2.3),
          };
        }
      } else if (analyser && !muted) {
        const rms = readAnalyserRms(analyser, inTimeBuf);
        bands = readAnalyserBands(analyser, inFreqBuf);
        targetLevel = Math.min(1, rms * 3.8 + bands.mid * 0.35);
      }

      const prev = smoothedLevelRef.current;
      const alpha = targetLevel > prev ? 0.36 : 0.14;
      const level = prev + (targetLevel - prev) * alpha;
      smoothedLevelRef.current = level;

      phaseRef.current += 0.022 + level * 0.055;
      const phase = phaseRef.current;

      let primaryRgb = '16, 185, 129';
      let secondaryRgb = '52, 211, 153';
      if (muted) {
        primaryRgb = '239, 68, 68';
        secondaryRgb = '248, 113, 113';
      } else if (callState === 'user_speaking') {
        primaryRgb = '34, 197, 94';
        secondaryRgb = '74, 222, 128';
      } else if (callState === 'unfinished_hold') {
        primaryRgb = '245, 158, 11';
        secondaryRgb = '251, 191, 36';
      } else if (callState === 'thinking' || callState === 'transcribing') {
        primaryRgb = '99, 102, 241';
        secondaryRgb = '16, 185, 129';
      }

      const glowRadius = baseRadius * (1.5 + level * 0.55);
      const grad = ctx.createRadialGradient(cx, cy, baseRadius * 0.6, cx, cy, glowRadius);
      grad.addColorStop(0, `rgba(${primaryRgb}, ${0.26 + level * 0.32})`);
      grad.addColorStop(0.55, `rgba(${secondaryRgb}, ${0.1 + level * 0.16})`);
      grad.addColorStop(1, `rgba(${primaryRgb}, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2);
      ctx.fill();

      const ringCount = 3;
      const segments = 72;
      for (let rIdx = 0; rIdx < ringCount; rIdx++) {
        const ringScale = 1.1 + rIdx * 0.12 + level * (0.18 + rIdx * 0.1);
        const ringBase = baseRadius * ringScale;
        const amp =
          (callState === 'thinking' || callState === 'transcribing'
            ? 3.2 + rIdx * 1.5
            : (2.5 + level * 14) * (1 + rIdx * 0.25)) * scale;

        ctx.beginPath();
        for (let i = 0; i <= segments; i++) {
          const theta = (i / segments) * Math.PI * 2;
          const harmonic1 = Math.sin(theta * 3 + phase * (rIdx % 2 === 0 ? 1 : -1.2));
          const harmonic2 = Math.cos(theta * 5 - phase * 1.4) * (0.45 + bands.mid * 0.8);
          const harmonic3 = Math.sin(theta * 7 + phase * 2.1) * (0.25 + bands.high * 0.7);
          const offset = (harmonic1 * 0.55 + harmonic2 * 0.3 + harmonic3 * 0.15) * amp;
          const rad = ringBase + offset;
          const x = cx + Math.cos(theta) * rad;
          const y = cy + Math.sin(theta) * rad;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();

        const ringAlpha = Math.max(0.12, 0.52 - rIdx * 0.14 + level * 0.25);
        ctx.strokeStyle =
          rIdx === 1 ? `rgba(${secondaryRgb}, ${ringAlpha})` : `rgba(${primaryRgb}, ${ringAlpha})`;
        ctx.lineWidth = rIdx === 0 ? 2.2 : 1.4;
        ctx.stroke();
      }

      if (callState === 'thinking' || callState === 'transcribing') {
        const orbitRadius = baseRadius * 1.3;
        const spin = now / 380;
        for (let a = 0; a < 2; a++) {
          const startAngle = spin + a * Math.PI;
          ctx.beginPath();
          ctx.arc(cx, cy, orbitRadius, startAngle, startAngle + Math.PI * 0.55);
          ctx.strokeStyle = a === 0 ? `rgba(${primaryRgb}, 0.85)` : `rgba(${secondaryRgb}, 0.75)`;
          ctx.lineWidth = 2.4;
          ctx.lineCap = 'round';
          ctx.stroke();
        }
      }
    };

    rafId = requestAnimationFrame(drawOrb);
    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', resize);
    };
  }, [callState, muted, analyser, outputAnalyser]);

  // Header waveform: thin bars scrolling right to left, faded at both edges.
  useEffect(() => {
    const canvas = waveCanvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    let rafId = 0;
    const history: number[] = new Array(WAVE_BARS).fill(0);
    let lastSampleAt = 0;
    const inBuf = new Uint8Array(new ArrayBuffer(analyser?.fftSize ?? 512));
    const outBuf = new Uint8Array(new ArrayBuffer(outputAnalyser?.fftSize ?? 512));

    const resize = () => fitCanvas(canvas, ctx);
    resize();
    window.addEventListener('resize', resize);

    const draw = (now: number) => {
      rafId = requestAnimationFrame(draw);
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      ctx.clearRect(0, 0, width, height);

      let level = 0;
      if (callState === 'speaking' && outputAnalyser) {
        level = Math.min(1, readAnalyserRms(outputAnalyser, outBuf) * 3.8);
      } else if (analyser && !muted && callState !== 'thinking' && callState !== 'transcribing') {
        level = Math.min(1, readAnalyserRms(analyser, inBuf) * 3.5);
      }
      if (lastSampleAt === 0) lastSampleAt = now;
      while (now - lastSampleAt >= WAVE_SAMPLE_MS) {
        history.push(level);
        history.shift();
        lastSampleAt += WAVE_SAMPLE_MS;
      }

      ctx.fillStyle = getComputedStyle(canvas).color;
      const slot = width / WAVE_BARS;
      const barWidth = Math.max(1, Math.min(2, slot * 0.45));
      const thinking = callState === 'thinking' || callState === 'transcribing';
      for (let i = 0; i < WAVE_BARS; i++) {
        const edge = Math.sin((Math.PI * (i + 0.5)) / WAVE_BARS);
        let h = Math.max(2, history[i] * height);
        let alpha = 0.25 + 0.75 * edge;
        if (thinking) {
          const wave = 0.5 + 0.5 * Math.sin(now / 260 - i * 0.35);
          h = 2 + wave * height * 0.18;
          alpha *= 0.35 + 0.65 * wave;
        }
        ctx.globalAlpha = alpha * (muted ? 0.4 : 1);
        ctx.fillRect(i * slot + (slot - barWidth) / 2, (height - h) / 2, barWidth, h);
      }
      ctx.globalAlpha = 1;
    };

    rafId = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', resize);
    };
  }, [callState, muted, analyser, outputAnalyser]);

  useEffect(() => {
    if (!settingsOpen) return;
    void navigator.mediaDevices
      ?.enumerateDevices()
      .then((devices) => setInputDevices(devices.filter((d) => d.kind === 'audioinput')))
      .catch(() => setInputDevices([]));
    const onPointerDown = (e: PointerEvent) => {
      if (!settingsRef.current?.contains(e.target as Node)) setSettingsOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [settingsOpen]);

  const stateLabel = muted
    ? 'Microphone muted'
    : callState === 'user_speaking'
      ? 'Listening to you…'
      : callState === 'unfinished_hold'
        ? 'Holding the floor, finish your thought…'
        : callState === 'transcribing'
          ? 'Transcribing…'
          : callState === 'thinking'
            ? activeToolLabel || 'Thinking…'
            : callState === 'speaking'
              ? 'Speaking · talk to interrupt'
              : 'Listening';

  const activeSubtitle =
    callState === 'speaking' && currentAgentSentence
      ? { speaker: agentName, text: currentAgentSentence }
      : partialTranscript
        ? { speaker: 'You', text: `${partialTranscript}…` }
        : lastUserTranscript && isWorking
          ? { speaker: 'You', text: lastUserTranscript }
          : null;

  const voiceApplies = settings.language === 'en';

  return (
    <div
      className="chat-voice-call-stage"
      role="region"
      aria-label={`Voice call with ${agentName}`}
      data-call-state={callState}
    >
      <div className="chat-voice-call-stage-header">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="text-xs font-semibold text-foreground">Voice chat</span>
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {formatDuration(seconds)}
          </span>
        </div>
        <canvas ref={waveCanvasRef} className="chat-voice-call-wave" aria-hidden="true" />
      </div>

      <div className="chat-voice-call-stage-center">
        <div className="chat-voice-call-orb-wrap">
          <canvas ref={orbCanvasRef} className="chat-voice-call-orb-canvas" aria-hidden="true" />
          <div
            className={cn(
              'chat-voice-call-stage-avatar',
              callState === 'speaking' && 'is-speaking',
              callState === 'user_speaking' && 'is-user-speaking',
              callState === 'unfinished_hold' && 'is-holding',
            )}
          >
            {resolvedLogoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={resolvedLogoUrl} alt={agentName} className="h-full w-full object-cover" />
            ) : (
              <Bot size={28} />
            )}
          </div>
        </div>

        <h3 className="text-sm font-semibold tracking-tight text-foreground">{agentName}</h3>
        <div
          className="flex items-center gap-1.5 text-xs text-muted-foreground"
          role="status"
          aria-live="polite"
        >
          {isWorking && <Loader2 size={12} className="shrink-0 animate-spin" />}
          <span>{stateLabel}</span>
        </div>

        {activeToolLabel && (callState === 'thinking' || callState === 'speaking') && (
          <div className="chat-voice-call-tool-pill">
            {activeToolLabel.toLowerCase().startsWith('routing') ? (
              <Sparkles size={12} className="shrink-0" />
            ) : (
              <Wrench size={12} className="shrink-0" />
            )}
            <span className="truncate">{activeToolLabel}</span>
          </div>
        )}

        {captionsEnabled && activeSubtitle && (
          <div className="chat-voice-call-subtitle">
            <span className="chat-voice-call-subtitle-speaker">{activeSubtitle.speaker}:</span>{' '}
            <span>“{activeSubtitle.text}”</span>
          </div>
        )}
      </div>

      <div className="chat-voice-call-controls">
        <button
          type="button"
          onClick={onToggleMute}
          className={cn('chat-voice-call-control-btn', muted && 'is-danger')}
          aria-pressed={muted}
          title={muted ? 'Unmute microphone' : 'Mute microphone'}
        >
          {muted ? <MicOff size={16} /> : <Mic size={16} />}
          <span className="chat-voice-call-control-label">{muted ? 'Unmute' : 'Mute'}</span>
        </button>

        <div ref={settingsRef}>
          <button
            type="button"
            onClick={() => setSettingsOpen((v) => !v)}
            className={cn('chat-voice-call-control-btn', settingsOpen && 'is-active')}
            aria-expanded={settingsOpen}
            aria-haspopup="dialog"
            title="Call settings"
          >
            <Settings2 size={16} />
            <span className="chat-voice-call-control-label">Settings</span>
          </button>
          {settingsOpen && (
            <div
              className="chat-voice-call-settings"
              role="dialog"
              aria-label="Call settings"
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  e.stopPropagation();
                  setSettingsOpen(false);
                }
              }}
            >
              <label className="chat-voice-call-settings-field">
                <span>Spoken language</span>
                <select
                  value={settings.language}
                  onChange={(e) =>
                    onChangeSettings({ language: e.target.value as CallLanguageSetting })
                  }
                >
                  {CALL_LANGUAGES.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="chat-voice-call-settings-field">
                <span>Voice{voiceApplies ? '' : ' (English only)'}</span>
                <select
                  value={voiceApplies ? settings.voice : ''}
                  disabled={!voiceApplies}
                  onChange={(e) => onChangeSettings({ voice: e.target.value })}
                >
                  {CALL_VOICES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="chat-voice-call-settings-field">
                <span>Microphone</span>
                <select
                  value={settings.inputDeviceId}
                  onChange={(e) => onChangeSettings({ inputDeviceId: e.target.value })}
                >
                  <option value="">System default</option>
                  {inputDevices
                    .filter((d) => d.deviceId && d.deviceId !== 'default')
                    .map((d, i) => (
                      <option key={d.deviceId} value={d.deviceId}>
                        {d.label || `Microphone ${i + 1}`}
                      </option>
                    ))}
                </select>
              </label>
              <p className="chat-voice-call-settings-hint">
                Talk over {agentName} or press Esc to interrupt.
              </p>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => setCaptionsEnabled((v) => !v)}
          className={cn('chat-voice-call-control-btn', captionsEnabled && 'is-active')}
          aria-pressed={captionsEnabled}
          title={captionsEnabled ? 'Hide captions' : 'Show captions'}
        >
          {captionsEnabled ? <Captions size={16} /> : <CaptionsOff size={16} />}
          <span className="chat-voice-call-control-label">Captions</span>
        </button>

        <button
          type="button"
          onClick={onEndCall}
          className="chat-voice-call-control-btn is-hangup"
          title="End voice call"
        >
          <PhoneOff size={16} />
          <span className="chat-voice-call-control-label">End</span>
        </button>
      </div>
    </div>
  );
}
