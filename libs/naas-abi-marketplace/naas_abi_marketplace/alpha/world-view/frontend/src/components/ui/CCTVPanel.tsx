'use client';
import { useEffect, useRef, useState, useCallback } from 'react';
import type { CCTVCamera } from '@/lib/types';

interface CCTVPanelProps {
  camera: CCTVCamera;
  onClose: () => void;
}

function proxyUrl(url: string) {
  if (!url) return '';
  return `/api/cctv/snapshot?url=${encodeURIComponent(url)}`;
}

const SOURCE_LABELS: Record<string, string> = {
  nyc: '511NY.ORG',
  london: 'TFL.GOV.UK',
  openwebcamdb: 'OPENWEBCAMDB.COM',
};

export default function CCTVPanel({ camera, onClose }: CCTVPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [status, setStatus]       = useState<'loading' | 'resolving' | 'live' | 'error'>('loading');
  const [imgSrc, setImgSrc]       = useState('');
  const [streamUrl, setStreamUrl] = useState(camera.videoUrl);
  const [streamType, setStreamType] = useState<'hls' | 'mp4' | 'youtube'>(camera.type);
  const imgTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // For OpenWebcamDB cameras: stream URL must be fetched on-demand
  const resolveStream = useCallback(async () => {
    if (camera.source !== 'openwebcamdb' || !camera.slug) return;
    setStatus('resolving');
    try {
      const res = await fetch(`/api/webcams/stream?slug=${encodeURIComponent(camera.slug)}`);
      if (!res.ok) { setStatus('error'); return; }
      const data = (await res.json()) as { url: string; type: string };
      if (!data.url) { setStatus('error'); return; }
      setStreamUrl(data.url);
      setStreamType(data.type as 'hls' | 'mp4' | 'youtube');
      setStatus('loading');
    } catch {
      setStatus('error');
    }
  }, [camera.slug, camera.source]);

  useEffect(() => {
    if (camera.source === 'openwebcamdb') {
      resolveStream();
    }
  }, [camera.source, resolveStream]);

  const isHLS     = streamType === 'hls';
  const isMP4     = streamType === 'mp4';
  const isYouTube = streamType === 'youtube';

  // Thumbnail / HLS snapshot refresh loop
  useEffect(() => {
    if (isYouTube || status === 'resolving') return;
    if (imgTimerRef.current) clearInterval(imgTimerRef.current);

    if (isMP4 && streamUrl) return; // handled by <video>

    if (isHLS && streamUrl) {
      const refresh = () => setImgSrc(proxyUrl(streamUrl) + `&t=${Date.now()}`);
      refresh();
      imgTimerRef.current = setInterval(refresh, 3000);
    } else if (camera.imageUrl) {
      const refresh = () => setImgSrc(proxyUrl(camera.imageUrl) + `&t=${Date.now()}`);
      refresh();
      imgTimerRef.current = setInterval(refresh, 5000);
    }

    return () => { if (imgTimerRef.current) clearInterval(imgTimerRef.current); };
  }, [isHLS, isMP4, isYouTube, streamUrl, camera.imageUrl, status]);

  // MP4 video playback
  useEffect(() => {
    const vid = videoRef.current;
    if (!vid || !isMP4 || !streamUrl) return;
    vid.src = proxyUrl(streamUrl);
    vid.load();
    const onPlaying = () => setStatus('live');
    const onError = () => {
      if (camera.imageUrl) { setImgSrc(proxyUrl(camera.imageUrl)); setStatus('live'); }
      else setStatus('error');
    };
    vid.addEventListener('playing', onPlaying);
    vid.addEventListener('error', onError);
    vid.play().catch(onError);
    return () => {
      vid.removeEventListener('playing', onPlaying);
      vid.removeEventListener('error', onError);
      vid.pause(); vid.src = '';
    };
  }, [isMP4, streamUrl, camera.imageUrl]);

  const now = new Date().toLocaleTimeString('en-GB', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });

  const sourceLabel = SOURCE_LABELS[camera.source] ?? camera.source?.toUpperCase();

  return (
    <div
      className="absolute bottom-20 right-4 z-30 font-mono text-xs"
      style={{ width: 380, background: 'rgba(0,0,0,0.93)', border: '1px solid rgba(255,51,102,0.4)', backdropFilter: 'blur(8px)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-pink-500/20">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          <span className="text-[10px] text-pink-400/60 tracking-widest uppercase">CCTV FEED</span>
          <span className="text-[10px] text-red-400 tracking-wider font-bold">● REC</span>
        </div>
        <button onClick={onClose} className="text-pink-400/40 hover:text-pink-300 px-1">✕</button>
      </div>

      {/* Camera metadata */}
      <div className="px-3 py-1 border-b border-pink-500/10 space-y-0.5">
        <div className="text-pink-200 tracking-wider uppercase text-[11px] font-medium truncate">{camera.name}</div>
        <div className="flex gap-3 text-pink-400/50 text-[10px]">
          <span>{(camera.country ?? camera.city).toUpperCase()}</span>
          <span>{camera.lat.toFixed(4)}°N</span>
          <span>{Math.abs(camera.lon).toFixed(4)}°{camera.lon < 0 ? 'W' : 'E'}</span>
        </div>
      </div>

      {/* Video feed area */}
      <div className="relative bg-black" style={{ height: 214 }}>
        {/* Scanline overlay */}
        <div className="absolute inset-0 z-10 pointer-events-none opacity-30"
          style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.3) 2px, rgba(0,0,0,0.3) 4px)' }} />

        {/* Resolving stream URL */}
        {status === 'resolving' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 z-5">
            <span className="text-[10px] text-pink-400/60 tracking-widest animate-pulse">RESOLVING STREAM...</span>
            <span className="text-[9px] text-pink-400/30">CONNECTING TO OPENWEBCAMDB</span>
          </div>
        )}

        {/* Error state */}
        {status === 'error' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-5 px-4">
            <div className="absolute inset-0 opacity-5"
              style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'4\' height=\'4\'%3E%3Crect width=\'1\' height=\'1\' x=\'0\' y=\'0\' fill=\'%23ff3366\'/%3E%3Crect width=\'1\' height=\'1\' x=\'2\' y=\'2\' fill=\'%23ff3366\'/%3E%3C/svg%3E")' }} />
            <div className="text-pink-400/30 text-3xl">▦</div>
            <div className="text-center space-y-1">
              <div className="text-[10px] text-pink-300/50 tracking-widest">STREAM UNAVAILABLE</div>
              <div className="text-[9px] text-pink-400/30 tracking-wide">
                {streamType === 'hls' ? 'HLS STREAM — DIRECT BROWSER ACCESS RESTRICTED' : 'SIGNAL LOST — RECONNECTING'}
              </div>
            </div>
            <div className="border border-pink-500/20 p-2 w-full space-y-1 text-[9px] text-pink-400/50">
              <div className="flex justify-between"><span>LOCATION</span><span className="text-pink-300/60 truncate max-w-36 text-right">{camera.name}</span></div>
              <div className="flex justify-between"><span>COORDINATES</span><span className="text-pink-300/60">{camera.lat.toFixed(4)}° {camera.lon.toFixed(4)}°</span></div>
              <div className="flex justify-between"><span>PROTOCOL</span><span className="text-pink-300/60">{streamType.toUpperCase()}</span></div>
            </div>
          </div>
        )}

        {/* Loading */}
        {status === 'loading' && (
          <div className="absolute inset-0 flex items-center justify-center z-5">
            <span className="text-[10px] text-pink-400/50 tracking-widest animate-pulse">ACQUIRING SIGNAL...</span>
          </div>
        )}

        {/* ── YouTube embed ────────────────────────────────────────────────────── */}
        {isYouTube && streamUrl && (
          <iframe
            src={streamUrl}
            className="absolute inset-0 w-full h-full"
            allow="autoplay; encrypted-media; picture-in-picture"
            allowFullScreen
            onLoad={() => setStatus('live')}
            style={{ border: 'none' }}
          />
        )}

        {/* Thumbnail for OpenWebcamDB (shown while YouTube is loading or as fallback) */}
        {isYouTube && camera.imageUrl && status !== 'live' && (
          <img
            src={proxyUrl(camera.imageUrl)}
            alt={camera.name}
            className="absolute inset-0 w-full h-full object-cover z-1"
            onLoad={() => { /* keep loading state until iframe ready */ }}
            onError={() => {}}
          />
        )}

        {/* ── HLS snapshot (proxied from server) ─────────────────────────────── */}
        {imgSrc && !isMP4 && !isYouTube && (
          <img
            src={imgSrc}
            alt={camera.name}
            className="absolute inset-0 w-full h-full object-cover"
            onLoad={() => setStatus('live')}
            onError={() => setStatus('error')}
          />
        )}

        {/* ── MP4 JPEG fallback ────────────────────────────────────────────────── */}
        {imgSrc && isMP4 && status !== 'live' && (
          <img
            src={imgSrc}
            alt={camera.name}
            className="absolute inset-0 w-full h-full object-cover"
            onLoad={() => setStatus('live')}
            onError={() => {}}
          />
        )}

        {/* ── MP4 video ────────────────────────────────────────────────────────── */}
        {isMP4 && (
          <video
            ref={videoRef}
            className="absolute inset-0 w-full h-full object-cover"
            muted autoPlay loop playsInline
          />
        )}

        {/* Corner brackets */}
        {(['top-1.5 left-1.5', 'top-1.5 right-1.5', 'bottom-1.5 left-1.5', 'bottom-1.5 right-1.5'] as const).map((cls) => {
          const isRight  = cls.includes('right');
          const isBottom = cls.includes('bottom');
          return (
            <div key={cls} className={`absolute ${cls} w-4 h-4 z-20 pointer-events-none`} style={{
              borderTop:    isBottom ? 'none' : '1.5px solid rgba(255,51,102,0.5)',
              borderBottom: isBottom ? '1.5px solid rgba(255,51,102,0.5)' : 'none',
              borderLeft:   isRight  ? 'none' : '1.5px solid rgba(255,51,102,0.5)',
              borderRight:  isRight  ? '1.5px solid rgba(255,51,102,0.5)' : 'none',
            }} />
          );
        })}

        {status === 'live' && (
          <div className="absolute bottom-1.5 left-2 z-20 text-[9px] text-pink-300/60 tracking-wider">
            {now} UTC
          </div>
        )}

        <div className="absolute top-1.5 right-2 z-20 text-[8px] text-pink-400/30 tracking-wider">
          ID:{camera.id.replace(/[^a-z0-9]/gi, '').slice(-8).toUpperCase()}
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 flex items-center justify-between text-[9px] border-t border-pink-500/10">
        <span className="text-pink-400/40">
          {camera.source === 'openwebcamdb'
            ? <a href="https://openwebcamdb.com" target="_blank" rel="noreferrer" className="hover:text-pink-300/60 transition-colors">Powered by OpenWebcamDB.com</a>
            : `SRC: ${sourceLabel}`
          }
        </span>
        <span className={
          status === 'live'      ? 'text-green-400 font-medium' :
          status === 'error'     ? 'text-red-400' :
          status === 'resolving' ? 'text-yellow-300 animate-pulse' :
                                   'text-yellow-400 animate-pulse'
        }>
          {status === 'live'      ? '◉ SIGNAL OK' :
           status === 'error'     ? '◎ NO SIGNAL' :
           status === 'resolving' ? '◌ RESOLVING' :
                                    '◌ CONNECTING'}
        </span>
      </div>
    </div>
  );
}
