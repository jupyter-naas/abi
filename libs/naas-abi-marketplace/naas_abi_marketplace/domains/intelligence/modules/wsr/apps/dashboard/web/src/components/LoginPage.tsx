'use client';

import { useState, useRef, useEffect } from 'react';
import { login } from '@/lib/auth';

interface Props {
  onSuccess: () => void;
}

export default function LoginPage({ onSuccess }: Props) {
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [dots, setDots]         = useState('');
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  // Animate "INITIALISING..." dots
  useEffect(() => {
    const t = setInterval(() => setDots(d => d.length >= 3 ? '' : d + '.'), 500);
    return () => clearInterval(t);
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    setTimeout(() => {
      if (login(email, password)) {
        onSuccess();
      } else {
        setError('ACCESS DENIED — invalid credentials');
        setLoading(false);
      }
    }, 600);
  }

  return (
    <div className="w-screen h-screen bg-black flex flex-col items-center justify-center select-none">

      {/* Scanline overlay */}
      <div
        className="pointer-events-none fixed inset-0 z-50"
        style={{
          background:
            'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.07) 2px, rgba(0,0,0,0.07) 4px)',
        }}
      />

      {/* Header */}
      <div className="mb-10 text-center space-y-1">
        <div className="text-green-400 text-2xl tracking-[0.3em] font-mono font-bold">
          ◉ WORLD SITUATION ROOM
        </div>
        <div className="text-green-500/40 text-xs tracking-widest font-mono">
          GEOSPATIAL INTELLIGENCE PLATFORM — RESTRICTED ACCESS
        </div>
      </div>

      {/* Terminal box */}
      <div
        className="w-full max-w-sm font-mono border border-green-500/30 bg-black/80 p-8"
        style={{ boxShadow: '0 0 40px rgba(0,255,65,0.08)' }}
      >
        {/* System status line */}
        <div className="text-green-500/50 text-xs tracking-widest mb-6 flex items-center gap-2">
          <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          SYSTEM ONLINE — AUTHENTICATE TO PROCEED
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email */}
          <div className="space-y-1">
            <label className="text-green-500/60 text-xs tracking-widest block">
              OPERATOR ID (EMAIL)
            </label>
            <div className="flex items-center border border-green-500/20 bg-black focus-within:border-green-400/60 transition-colors">
              <span className="px-3 text-green-500/40 text-xs select-none">&gt;_</span>
              <input
                ref={emailRef}
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="flex-1 bg-transparent text-green-400 text-sm py-2.5 pr-3 outline-none placeholder:text-green-500/20 tracking-wider"
                placeholder="operator@domain.com"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-1">
            <label className="text-green-500/60 text-xs tracking-widest block">
              ACCESS CODE
            </label>
            <div className="flex items-center border border-green-500/20 bg-black focus-within:border-green-400/60 transition-colors">
              <span className="px-3 text-green-500/40 text-xs select-none">&gt;_</span>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="flex-1 bg-transparent text-green-400 text-sm py-2.5 pr-3 outline-none placeholder:text-green-500/20 tracking-wider"
                placeholder="••••••••"
              />
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="border border-red-500/40 bg-red-900/10 px-3 py-2 text-red-400 text-xs tracking-wider">
              ⚠ {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 border text-xs tracking-[0.3em] font-bold transition-all disabled:opacity-40"
            style={{
              borderColor: 'rgba(0,255,65,0.5)',
              color: loading ? 'rgba(0,255,65,0.4)' : '#00ff41',
              background: loading ? 'rgba(0,255,65,0.03)' : 'transparent',
            }}
            onMouseEnter={e => {
              if (!loading) {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,255,65,0.08)';
              }
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
            }}
          >
            {loading ? `AUTHENTICATING${dots}` : 'ENTER SITUATION ROOM'}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-green-500/10 text-green-500/25 text-xs tracking-widest text-center">
          CLASSIFIED — AUTHORISED PERSONNEL ONLY
        </div>
      </div>

      {/* Bottom status bar */}
      <div className="mt-8 text-green-500/20 text-xs tracking-widest font-mono flex gap-6">
        <span>SYS: NOMINAL</span>
        <span>FEEDS: LIVE</span>
        <span>ENCRYPTION: AES-256</span>
      </div>
    </div>
  );
}
