'use client';

/**
 * IntelTicker
 *
 * Full-width scrolling news strip pinned directly below the navbar.
 * Must be rendered as a direct child of the root positioned container
 * so that absolute left-0 right-0 references the viewport, not a panel wrapper.
 *
 * Navbar height:  h-9  = 36px  → top-9
 * Ticker height:  h-6  = 24px
 * Bottom edge:    36 + 24 = 60px → side panels should start at top-[60px]
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { NewsItem } from '@/lib/types';

const _API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

const SEVERITY_BADGE: Record<NewsItem['severity'], string> = {
  breaking: 'bg-red-500 text-black',
  alert:    'bg-orange-500 text-black',
  update:   'bg-green-800 text-green-200',
};

export default function IntelTicker() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const tickerRef = useRef<HTMLDivElement>(null);
  const animRef   = useRef<number | null>(null);

  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch(`${_API_BASE}/api/news`);
      if (res.ok) setNews(await res.json());
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchNews();
    const id = setInterval(fetchNews, 3 * 60 * 1000);
    return () => clearInterval(id);
  }, [fetchNews]);

  // Seamless RTL scroll animation
  useEffect(() => {
    const el = tickerRef.current;
    if (!el || news.length === 0) return;

    let x = 0;
    function step() {
      x -= 0.5;
      const halfWidth = el!.scrollWidth / 2;
      if (Math.abs(x) >= halfWidth) x = 0;
      el!.style.transform = `translateX(${x}px)`;
      animRef.current = requestAnimationFrame(step);
    }

    animRef.current = requestAnimationFrame(step);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [news]);

  if (news.length === 0) return null;

  return (
    <div
      className="absolute top-9 left-0 right-0 h-6 z-20 flex items-center overflow-hidden border-b border-green-900/40"
      style={{ background: 'rgba(0,0,0,0.88)' }}
    >
      {/* Label pill */}
      <div className="shrink-0 px-2 h-full flex items-center font-mono text-[10px] text-red-400 tracking-widest border-r border-red-700/50 whitespace-nowrap">
        INTEL FEED
      </div>

      {/* Scrolling content — overflow-hidden clips the moving strip */}
      <div className="flex-1 overflow-hidden h-full flex items-center">
        <div ref={tickerRef} className="flex whitespace-nowrap" style={{ willChange: 'transform' }}>
          {[...news, ...news].map((item, i) => (
            <span
              key={`${item.id}-${i}`}
              className="inline-flex items-center gap-1.5 px-3 font-mono text-[10px] cursor-pointer hover:opacity-80"
              onClick={() => item.url && window.open(item.url, '_blank')}
            >
              <span className={`text-[9px] px-1 py-0.5 font-bold ${SEVERITY_BADGE[item.severity]}`}>
                {item.severity.toUpperCase()}
              </span>
              <span className={
                item.severity === 'breaking' ? 'text-red-300' :
                item.severity === 'alert'    ? 'text-orange-300' :
                                               'text-green-400/80'
              }>
                [{item.source}]
              </span>
              <span className="text-gray-300">{item.title}</span>
              <span className="text-gray-500 text-[9px] font-mono">
                {new Date(item.pubDate).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })}Z
              </span>
              <span className="text-gray-600 mx-3">◆</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
