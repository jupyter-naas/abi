'use client';

import { useEffect, useState, useCallback } from 'react';
import type { NewsItem, ConflictEvent } from '@/lib/types';

const _API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

interface Props {
  onFlyTo: (lat: number, lon: number, alt?: number) => void;
}

const SEVERITY_COLOR: Record<NewsItem['severity'], string> = {
  breaking: 'text-red-400 border-red-500/60 bg-red-950/40',
  alert: 'text-orange-400 border-orange-500/60 bg-orange-950/30',
  update: 'text-green-400 border-green-500/30 bg-green-950/20',
};

const SEVERITY_BADGE: Record<NewsItem['severity'], string> = {
  breaking: 'bg-red-500 text-black',
  alert: 'bg-orange-500 text-black',
  update: 'bg-green-800 text-green-200',
};

const CONFLICT_COLOR: Record<ConflictEvent['type'], string> = {
  nuclear: 'text-yellow-400',
  strike: 'text-red-400',
  base: 'text-blue-400',
  naval: 'text-cyan-400',
  zone: 'text-orange-400',
  capital: 'text-red-300',
};

const CONFLICT_ICON: Record<ConflictEvent['type'], string> = {
  nuclear: '☢',
  strike: '💥',
  base: '✈',
  naval: '⚓',
  zone: '⚠',
  capital: '🏛',
};

function timeAgo(ms: number): string {
  const diff = Date.now() - ms;
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function IntelPanel({ onFlyTo }: Props) {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [conflict, setConflict] = useState<ConflictEvent[]>([]);
  const [tab, setTab] = useState<'news' | 'sites'>('news');
  const [collapsed, setCollapsed] = useState(false);
  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch(`${_API_BASE}/api/news`);
      if (res.ok) setNews(await res.json());
    } catch { /* silent */ }
  }, []);

  const fetchConflict = useCallback(async () => {
    try {
      const res = await fetch(`${_API_BASE}/api/conflict-events`);
      if (res.ok) setConflict(await res.json());
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchNews();
    fetchConflict();
    const ni = setInterval(fetchNews, 3 * 60 * 1000);
    return () => clearInterval(ni);
  }, [fetchNews, fetchConflict]);

  const breakingCount = news.filter((n) => n.severity === 'breaking').length;
  const alertCount = news.filter((n) => n.severity === 'alert').length;

  const threatLevel =
    breakingCount >= 5 ? 'IMMINENT' :
    breakingCount >= 3 ? 'HIGH' :
    breakingCount >= 1 || alertCount >= 3 ? 'ELEVATED' :
    'MONITORING';

  const threatColor =
    threatLevel === 'IMMINENT' ? 'text-red-400 border-red-500' :
    threatLevel === 'HIGH' ? 'text-orange-400 border-orange-500' :
    threatLevel === 'ELEVATED' ? 'text-yellow-400 border-yellow-600' :
    'text-green-400 border-green-700';

  return (
    <>
      {/* ── Intel panel (left side) ───────────────────────────────────────── */}
      <div className="flex flex-col gap-1">
        {/* Header */}
        <div
          className={`border font-mono text-[10px] tracking-widest px-2 py-1 flex items-center justify-between cursor-pointer ${threatColor} bg-black/80`}
          onClick={() => setCollapsed((p) => !p)}
        >
          <span>◉ THEATER INTEL</span>
          <span className={`text-[9px] px-1.5 py-0.5 border font-bold ${threatColor} animate-pulse`}>
            {threatLevel}
          </span>
          <span className="text-gray-600">{collapsed ? '▸' : '▾'}</span>
        </div>

        {!collapsed && (
          <>
            {/* Tabs */}
            <div className="flex border-b border-green-900/40 font-mono text-[9px]">
              <button
                className={`px-2 py-1 tracking-widest ${tab === 'news' ? 'text-green-400 border-b border-green-500' : 'text-gray-600 hover:text-gray-400'}`}
                onClick={() => setTab('news')}
              >
                LIVE FEED {breakingCount > 0 && <span className="text-red-400">({breakingCount})</span>}
              </button>
              <button
                className={`px-2 py-1 tracking-widest ${tab === 'sites' ? 'text-green-400 border-b border-green-500' : 'text-gray-600 hover:text-gray-400'}`}
                onClick={() => setTab('sites')}
              >
                SITES ({conflict.length})
              </button>
            </div>

            {/* Content */}
            <div className="overflow-y-auto max-h-80 space-y-1 pr-0.5" style={{ scrollbarWidth: 'thin' }}>
              {tab === 'news' && news.map((item) => (
                <div
                  key={item.id}
                  className={`border-l-2 px-2 py-1.5 cursor-pointer hover:opacity-80 transition-opacity ${SEVERITY_COLOR[item.severity]}`}
                  onClick={() => item.url && window.open(item.url, '_blank')}
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className={`text-[8px] px-1 py-0.5 rounded font-bold ${SEVERITY_BADGE[item.severity]}`}>
                      {item.severity.toUpperCase()}
                    </span>
                    <span className="text-[9px] text-gray-500 font-mono">{item.source}</span>
                    <span className="text-[9px] text-gray-600 ml-auto font-mono">{timeAgo(item.pubDate)}</span>
                  </div>
                  <div className="font-mono text-[10px] leading-tight">{item.title}</div>
                </div>
              ))}

              {tab === 'sites' && conflict.map((site) => (
                <div
                  key={site.id}
                  className="border border-green-900/30 bg-black/60 px-2 py-1.5 cursor-pointer hover:border-green-600/50 transition-colors"
                  onClick={() => onFlyTo(site.lat, site.lon, site.severity === 'critical' ? 80000 : 150000)}
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className={`text-[12px] ${CONFLICT_COLOR[site.type]}`}>
                      {CONFLICT_ICON[site.type]}
                    </span>
                    <span className={`font-mono text-[10px] font-bold ${CONFLICT_COLOR[site.type]}`}>
                      {site.name}
                    </span>
                  </div>
                  <div className="font-mono text-[9px] text-gray-500">{site.country}</div>
                  <div className="font-mono text-[9px] text-gray-400 mt-0.5 leading-tight">{site.description}</div>
                  <div className="font-mono text-[8px] text-green-700 mt-0.5">↗ {site.lat.toFixed(3)}, {site.lon.toFixed(3)}</div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="font-mono text-[8px] text-gray-700 px-1 pt-1 border-t border-green-900/20">
              BBC · Al Jazeera · Reuters · airplanes.live · OSINT
            </div>
          </>
        )}
      </div>
    </>
  );
}
