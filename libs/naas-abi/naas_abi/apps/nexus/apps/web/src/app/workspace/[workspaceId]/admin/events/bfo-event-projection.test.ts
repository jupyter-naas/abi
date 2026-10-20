import { describe, expect, it } from 'vitest';
import {
  BFO_COLUMNS,
  EVENT_GRAPH_BUCKETS,
  UNKNOWN,
  buildEventGraphPayload,
  deriveProcessNaming,
  eventSentence,
  formatEventClock,
  formatEventDate,
  projectEventToBfo,
  summarizeBucket,
  type PlatformEvent,
} from './bfo-event-projection';

function baseEvent(overrides: Partial<PlatformEvent> = {}): PlatformEvent {
  return {
    _uri: 'http://ontology.naas.ai/abi/agent/evt-1',
    _class_uri: 'http://ontology.naas.ai/abi/agent/AgentToolCalled',
    _seq: 42,
    _stored_at: '2026-07-31T12:00:00Z',
    ...overrides,
  };
}

describe('projectEventToBfo', () => {
  it('uses book column order', () => {
    expect(BFO_COLUMNS.map((c) => c.key)).toEqual([
      'materialEntity',
      'process',
      'site',
      'ice',
      'quality',
      'realizable',
      'temporalRegion',
    ]);
  });

  it('maps ICE, site, process, and temporal from stored event metadata', () => {
    const buckets = projectEventToBfo(
      baseEvent({
        _site: 'deploy.example',
        created_at: '2026-07-31T12:01:00Z',
        user_id: 'user-123',
        tool_name: 'search',
        status: 'ok',
        latency_ms: 12,
      })
    );

    expect(buckets.ice).toBe('event-log#seq=42');
    expect(buckets.site).toBe('deploy.example');
    expect(buckets.process).toBe('AgentToolCalled');
    expect(buckets.temporalRegion).toBe('2026-07-31T12:01:00Z');
    expect(buckets.materialEntity).toBe('user-123');
    expect(buckets.realizable).toBe('search');
    expect(buckets.quality).toBe('ok · 12ms');
  });

  it('falls back to Unknown for unmapped material, quality, realizable', () => {
    const buckets = projectEventToBfo(baseEvent({ _site: 'deploy.example' }));
    expect(buckets.materialEntity).toBe(UNKNOWN);
    expect(buckets.quality).toBe(UNKNOWN);
    expect(buckets.realizable).toBe(UNKNOWN);
    expect(buckets.ice).not.toBe(UNKNOWN);
    expect(buckets.site).not.toBe(UNKNOWN);
  });

  it('uses Unknown for site when deploy host is absent', () => {
    const buckets = projectEventToBfo(baseEvent());
    expect(buckets.site).toBe(UNKNOWN);
  });

  it('uses agent_name as material when user_id is absent', () => {
    const buckets = projectEventToBfo(baseEvent({ agent_name: 'ResearchAgent' }));
    expect(buckets.materialEntity).toBe('ResearchAgent');
  });

  it('uses event URI for ICE when seq is missing', () => {
    const buckets = projectEventToBfo(
      baseEvent({ _seq: null, _uri: 'http://example.com/e1' })
    );
    expect(buckets.ice).toBe('http://example.com/e1');
  });
});

describe('deriveProcessNaming', () => {
  it('reads the verb off the trailing word of the class name', () => {
    const naming = deriveProcessNaming(
      baseEvent({ _class_uri: 'http://ontology.naas.ai/abi/agent/AgentUserMessageReceived' })
    );
    expect(naming.verb).toBe('RECEIVED');
    expect(naming.object).toBe('User Message');
  });

  it('splits acronyms in the class name rather than gluing them to the next word', () => {
    const naming = deriveProcessNaming(
      baseEvent({ _class_uri: 'http://ontology.naas.ai/abi/agent/AgentAIMessageEmitted' })
    );
    expect(naming.verb).toBe('EMITTED');
    expect(naming.object).toBe('AI Message');
  });

  it('prefers a payload field that names the object over the class name', () => {
    const naming = deriveProcessNaming(baseEvent({ tool_name: 'search_web' }));
    expect(naming.verb).toBe('CALLED');
    expect(naming.object).toBe('search_web');
  });

  it('falls back to Unknown when the class name carries no object', () => {
    const naming = deriveProcessNaming(
      baseEvent({ _class_uri: 'http://ontology.naas.ai/abi/agent/AgentRouted' })
    );
    expect(naming.verb).toBe('ROUTED');
    expect(naming.object).toBe(UNKNOWN);
  });
});

describe('buildEventGraphPayload', () => {
  it('gives every satellite bucket a node, populated or not', () => {
    const payload = buildEventGraphPayload(baseEvent());
    for (const bucket of EVENT_GRAPH_BUCKETS) {
      expect(payload.satellites.some((node) => node.bucket === bucket)).toBe(true);
    }
  });

  it('marks buckets with no payload backing as missing and dashes their node', () => {
    const payload = buildEventGraphPayload(baseEvent());
    expect(payload.missing).toContain('Quality');
    expect(payload.missing).toContain('Realizable');
    const quality = payload.satellites.find((node) => node.bucket === 'Quality');
    expect(quality?.known).toBe(false);
    expect(quality?.label).toBe(UNKNOWN);
    expect(quality?.fields).toEqual([]);
  });

  it('never reports GDC as missing: the stored log record is itself the evidence', () => {
    const payload = buildEventGraphPayload(baseEvent());
    expect(payload.missing).not.toContain('GDC');
    const gdc = payload.satellites.filter((node) => node.bucket === 'GDC');
    expect(gdc[0].label).toBe('event-log#seq=42');
  });

  it('reads participants, site, quality and realizable out of a populated payload', () => {
    const payload = buildEventGraphPayload(
      baseEvent({
        _site: 'nexus.localhost',
        workspace_id: 'ws-1',
        user_id: 'alice',
        agent_name: 'Abi',
        tool_name: 'search_web',
        content_length: 128,
        chat_id: 'thread-9',
      })
    );
    expect(payload.missing).toEqual([]);
    expect(summarizeBucket(payload, 'Material Entity')).toBe('alice · Abi');
    // A workspace is a GDC (configured information), not a site.
    expect(summarizeBucket(payload, 'Site')).toBe('nexus.localhost');
    expect(summarizeBucket(payload, 'GDC')).toContain('ws-1');
    expect(summarizeBucket(payload, 'Quality')).toBe('len=128');
    expect(summarizeBucket(payload, 'Realizable')).toBe('search_web');
    expect(eventSentence(payload)).toBe('alice · CALLED · search_web');
  });

  it('points the GDC relation at the process and the rest away from it', () => {
    const payload = buildEventGraphPayload(baseEvent({ user_id: 'alice' }));
    const gdc = payload.satellites.find((node) => node.bucket === 'GDC');
    const who = payload.satellites.find((node) => node.bucket === 'Material Entity');
    expect(gdc?.direction).toBe('in');
    expect(gdc?.predicate).toBe('is about');
    expect(who?.direction).toBe('out');
    expect(who?.predicate).toBe('has participant');
  });

  it('shows a temporal range only when the payload carries both ends', () => {
    const point = buildEventGraphPayload(baseEvent({ created_at: '2026-07-31T12:01:00Z' }));
    expect(summarizeBucket(point, 'Temporal Region')).not.toContain('→');

    const range = buildEventGraphPayload(
      baseEvent({ started_at: '2026-07-31T12:01:00Z', ended_at: '2026-07-31T12:02:00Z' })
    );
    expect(summarizeBucket(range, 'Temporal Region')).toContain('→');
  });
});

describe('timestamp formatting', () => {
  it('renders a parseable instant as clock and date', () => {
    expect(formatEventClock('2026-07-31T12:01:02Z')).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(formatEventDate('2026-07-31T12:01:02Z')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('falls back to Unknown rather than showing Invalid Date', () => {
    expect(formatEventClock('not-a-date')).toBe(UNKNOWN);
    expect(formatEventDate(null)).toBe(UNKNOWN);
  });
});

describe('identity resolved from graph/nexus-identity', () => {
  const identityEvent = (overrides: Partial<PlatformEvent> = {}): PlatformEvent =>
    baseEvent({
      _class_uri: 'http://ontology.naas.ai/nexus/ChangeWorkspaceMemberRole',
      _site: 'bob.example.com',
      actor_user_id: 'usr-1',
      target_user_id: 'usr-2',
      target_workspace_id: 'ws-1',
      membership_role: 'admin',
      previous_membership_role: 'member',
      _identity: {
        actor: {
          user_id: 'usr-1',
          name: 'Alice Martin',
          email: 'alice@example.com',
          is_superadmin: true,
          workspace_role: 'owner',
        },
        subject: { user_id: 'usr-2', name: 'Bob Stone', email: 'bob@example.com', workspace_role: 'admin' },
        workspace: { workspace_id: 'ws-1', name: 'Acme', slug: 'acme' },
      },
      ...overrides,
    });

  it('names the person behind the account, then who the process was for', () => {
    const payload = buildEventGraphPayload(identityEvent());
    expect(summarizeBucket(payload, 'Material Entity')).toBe('Alice Martin · Bob Stone');
    const alice = payload.satellites.find((n) => n.label === 'Alice Martin');
    expect(alice?.shared).toBe(true);
    expect(alice?.fields).toContainEqual({ label: 'actor_user_id', value: 'usr-1' });
  });

  it('keeps the workspace in HOW WE KNOW, not WHERE', () => {
    const payload = buildEventGraphPayload(identityEvent());
    expect(summarizeBucket(payload, 'Site')).toBe('bob.example.com');
    expect(summarizeBucket(payload, 'GDC')).toContain('Acme');
  });

  it('shows the access role the actor realized', () => {
    const payload = buildEventGraphPayload(identityEvent());
    expect(summarizeBucket(payload, 'Realizable')).toBe('Workspace owner · Platform superadmin');
  });

  it('shows a role change as the membership record it rewrote', () => {
    const payload = buildEventGraphPayload(identityEvent());
    expect(summarizeBucket(payload, 'GDC')).toContain('member → admin');
  });

  it('falls back to ids when the identity graph could not resolve them', () => {
    const payload = buildEventGraphPayload(identityEvent({ _identity: undefined }));
    expect(summarizeBucket(payload, 'Material Entity')).toBe('usr-1 · usr-2');
    expect(summarizeBucket(payload, 'GDC')).toContain('ws-1');
  });

  it('reads imperative Nexus class names verb first', () => {
    expect(deriveProcessNaming(identityEvent())).toMatchObject({
      verb: 'CHANGED',
      object: 'Workspace Member Role',
    });
    expect(
      deriveProcessNaming(baseEvent({ _class_uri: 'http://ontology.naas.ai/nexus/AddUserToWorkspace' })),
    ).toMatchObject({ verb: 'ADDED', object: 'User to Workspace' });
    expect(eventSentence(buildEventGraphPayload(identityEvent()))).toBe(
      'Alice Martin · CHANGED · Workspace Member Role',
    );
  });
});

describe('terminal (git author) actors', () => {
  const hash = 'a1b2c3d4'.padEnd(64, '0');

  it('labels an unresolved git author briefly instead of printing the hash', () => {
    const payload = buildEventGraphPayload(baseEvent({ actor_user_id: `email-sha256:${hash}`, agent_name: 'Git_Agent' }));
    expect(summarizeBucket(payload, 'Material Entity')).toBe('git author a1b2c3d4 · Git_Agent');
  });

  it('uses the person name once the hash resolves', () => {
    const payload = buildEventGraphPayload(
      baseEvent({
        actor_user_id: `email-sha256:${hash}`,
        _identity: { actor: { user_id: 'usr-2', name: 'Bob Stone' } },
      }),
    );
    expect(summarizeBucket(payload, 'Material Entity')).toBe('Bob Stone');
  });
});
