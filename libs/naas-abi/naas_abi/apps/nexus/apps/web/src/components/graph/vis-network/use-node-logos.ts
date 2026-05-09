'use client';

import { useCallback, useEffect, useState } from 'react';
import type { GraphNode } from '@/stores/knowledge-graph';

/**
 * Resolves an optional logo URL from a graph node's properties.
 *
 * Looks at a small fixed set of property keys (snake_case, camelCase, full
 * IRIs) so authors don't have to normalise upstream data.
 */
function readNodeLogoUrl(node: GraphNode): string | undefined {
  const properties = node.properties ?? {};
  const candidates: unknown[] = [
    properties.logo_url,
    properties.logoUrl,
    properties['logo url'],
    properties['http://ontology.naas.ai/nexus/logo_url'],
    properties['https://ontology.naas.ai/nexus/logo_url'],
    (node as GraphNode & { logo_url?: unknown }).logo_url,
    (node as GraphNode & { logoUrl?: unknown }).logoUrl,
  ];

  const found = candidates.find((value) => {
    if (typeof value !== 'string') return false;
    const normalized = value.trim();
    if (!normalized) return false;
    if (normalized.toLowerCase() === 'unknown') return false;
    return true;
  });
  return typeof found === 'string' ? found.trim() : undefined;
}

export interface UseNodeLogosResult {
  /** url → data URI cache. Re-renders the component when new logos resolve. */
  logoDataByUrl: Record<string, string>;
  /** Returns the candidate logo URL for a node, or undefined if none. */
  getNodeLogoUrl: (node: GraphNode) => string | undefined;
}

/**
 * Fetches and caches logo images for graph nodes as data URIs so they can be
 * embedded inside the SVG node card without per-paint network requests.
 *
 * The logo proxy is `/api/image-data?url=<encoded>` — same-origin so requests
 * carry session cookies and bypass CORS for arbitrary remote logos.
 */
export function useNodeLogos(nodes: GraphNode[]): UseNodeLogosResult {
  const [logoDataByUrl, setLogoDataByUrl] = useState<Record<string, string>>({});

  const getNodeLogoUrl = useCallback(readNodeLogoUrl, []);

  useEffect(() => {
    const urls = Array.from(
      new Set(
        nodes
          .map((n) => getNodeLogoUrl(n))
          .filter((u): u is string => Boolean(u)),
      ),
    );

    const missing = urls.filter((u) => !logoDataByUrl[u]);
    if (missing.length === 0) return;

    let cancelled = false;
    (async () => {
      const updates: Record<string, string> = {};
      await Promise.all(
        missing.map(async (url) => {
          try {
            const res = await fetch(`/api/image-data?url=${encodeURIComponent(url)}`);
            if (!res.ok) return;
            const json = (await res.json()) as { dataUri?: string };
            if (json.dataUri) updates[url] = json.dataUri;
          } catch {
            // Ignore broken/missing logos; nodes will render without them.
          }
        }),
      );
      if (cancelled) return;
      if (Object.keys(updates).length > 0) {
        setLogoDataByUrl((prev) => ({ ...prev, ...updates }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [getNodeLogoUrl, logoDataByUrl, nodes]);

  return { logoDataByUrl, getNodeLogoUrl };
}
