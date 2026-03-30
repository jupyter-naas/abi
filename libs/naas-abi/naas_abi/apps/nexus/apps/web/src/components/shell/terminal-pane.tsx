'use client';

/**
 * TerminalPane — xterm.js terminal connected to the PTY WebSocket backend.
 * Dynamically imported (no SSR) since xterm requires browser APIs.
 */

import '@xterm/xterm/css/xterm.css';
import { useEffect, useRef, useCallback } from 'react';
import { getApiUrl } from '@/lib/config';

export function TerminalPane({ visible }: { visible: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<import('@xterm/xterm').Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitRef = useRef<import('@xterm/addon-fit').FitAddon | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  const connect = useCallback(async () => {
    if (!containerRef.current) return;

    // Dynamic import — browser only
    const { Terminal } = await import('@xterm/xterm');
    const { FitAddon } = await import('@xterm/addon-fit');

    // Tear down any existing session
    termRef.current?.dispose();
    wsRef.current?.close();

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: '"JetBrains Mono", "Cascadia Code", Menlo, monospace',
      theme: {
        background: '#0d1117',
        foreground: '#e6edf3',
        cursor: '#58a6ff',
        selectionBackground: '#264f78',
        black: '#484f58', red: '#ff7b72', green: '#3fb950',
        yellow: '#d29922', blue: '#58a6ff', magenta: '#bc8cff',
        cyan: '#39c5cf', white: '#b1bac4',
        brightBlack: '#6e7681', brightRed: '#ffa198', brightGreen: '#56d364',
        brightYellow: '#e3b341', brightBlue: '#79c0ff', brightMagenta: '#d2a8ff',
        brightCyan: '#56d4dd', brightWhite: '#f0f6fc',
      },
      allowTransparency: false,
      scrollback: 5000,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;
    fitRef.current = fitAddon;

    // WebSocket URL: swap http(s) → ws(s)
    const apiBase = getApiUrl().replace(/^http/, 'ws');
    const ws = new WebSocket(`${apiBase}/api/lab/terminal/ws`);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      // Send initial size
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    };

    ws.onmessage = (ev) => {
      const data = ev.data instanceof ArrayBuffer
        ? new Uint8Array(ev.data)
        : ev.data;
      term.write(data);
    };

    ws.onclose = () => {
      term.write('\r\n\x1b[33m[connection closed — click to reconnect]\x1b[0m\r\n');
    };

    ws.onerror = () => {
      term.write('\r\n\x1b[31m[WebSocket error]\x1b[0m\r\n');
    };

    // Keyboard → PTY
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });

    // Resize → PTY
    term.onResize(({ cols, rows }) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols, rows }));
      }
    });

    // ResizeObserver → fit
    resizeObserverRef.current?.disconnect();
    const ro = new ResizeObserver(() => {
      try { fitAddon.fit(); } catch { /* ignore mid-unmount */ }
    });
    if (containerRef.current) ro.observe(containerRef.current);
    resizeObserverRef.current = ro;
  }, []);

  // Mount terminal when first made visible
  useEffect(() => {
    if (!visible) return;
    // Tiny delay so the container has rendered its full height
    const t = setTimeout(() => connect(), 80);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  // Fit on visibility toggle
  useEffect(() => {
    if (visible) {
      setTimeout(() => { try { fitRef.current?.fit(); } catch { /* */ } }, 100);
    }
  }, [visible]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
      wsRef.current?.close();
      termRef.current?.dispose();
    };
  }, []);

  return (
    <div className="flex h-full flex-col bg-[#0d1117]">
      {/* Title bar */}
      <div className="flex h-7 shrink-0 items-center justify-between border-b border-white/10 px-3">
        <span className="text-[11px] font-medium text-white/50 uppercase tracking-widest">Terminal</span>
        <button
          onClick={connect}
          title="New terminal / reconnect"
          className="rounded px-2 py-0.5 text-[10px] text-white/40 hover:bg-white/10 hover:text-white/70"
        >
          ↺ New
        </button>
      </div>
      {/* xterm.js mount point */}
      <div ref={containerRef} className="flex-1 overflow-hidden p-1" />
    </div>
  );
}
