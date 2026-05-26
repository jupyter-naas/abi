export interface OpencodeSession {
  id: string;
  title?: string;
  parentID?: string;
  updatedAt?: string;
}

export function buildSessionTree(
  sessions: OpencodeSession[],
): Array<{ session: OpencodeSession; depth: number }> {
  if (sessions.length === 0) return [];

  const byId = new Map(sessions.map((s) => [s.id, s]));
  const childrenOf = new Map<string, OpencodeSession[]>();
  for (const session of sessions) {
    const parentKey =
      session.parentID && byId.has(session.parentID) ? session.parentID : '';
    const bucket = childrenOf.get(parentKey) ?? [];
    bucket.push(session);
    childrenOf.set(parentKey, bucket);
  }

  const sortByUpdated = (a: OpencodeSession, b: OpencodeSession) =>
    new Date(b.updatedAt ?? 0).getTime() - new Date(a.updatedAt ?? 0).getTime();

  const tree: Array<{ session: OpencodeSession; depth: number }> = [];
  const walk = (parentKey: string, depth: number) => {
    for (const session of [...(childrenOf.get(parentKey) ?? [])].sort(sortByUpdated)) {
      tree.push({ session, depth });
      walk(session.id, depth + 1);
    }
  };
  walk('', 0);
  return tree;
}

export function sessionDisplayTitle(
  session: OpencodeSession | undefined,
  fallbackId: string,
): string {
  if (session?.title) return session.title;
  if (fallbackId.startsWith('nexus-')) return 'New session';
  return fallbackId.slice(0, 24);
}
