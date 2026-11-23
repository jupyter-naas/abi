// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearResources } from '@/lib/resource-cache';
import { clearOrgBrandingCache, loadOrgBranding } from '@/lib/org-branding';
import { readOrganization, readOrganizationDomains } from '@/lib/organization-resource';
import { SETTINGS_CACHE_HEADER } from '@/lib/settings-cache';
import { clearViewFlag } from '@/lib/view-flag';
import {
  SETTINGS_RECONCILE_MS,
  ensureAgentsSynced,
  forgetAgentsSync,
  readAgentRoster,
  useAgentsStore,
} from './agents';
import { authFetch, useAuthStore, type User } from './auth';
import { invalidateModelCatalog, readAvailableProviders, readProviderModels, useModelsStore } from './models';
import { useIntegrationsStore } from './integrations';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));

const person = (id: string): User => ({ id, email: `${id}@example.invalid`, name: id, createdAt: new Date() });

const roster = [
  {
    id: 'abi',
    workspace_id: 'ws-1',
    name: 'Abi',
    description: 'The default',
    class_name: 'naas_abi.agents/AbiAgent',
    system_prompt: 'Be helpful.',
    model_id: 'claude-sonnet-5',
    provider: 'anthropic',
    is_default: true,
    intents: [{ intent_value: 'ask', intent_type: 'AGENT', intent_target: 'helper', intent_scope: 'workspace' }],
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
];

/** What the browser asked the API, as "METHOD /path". */
let calls: string[] = [];
let headers: Headers[] = [];

function fakeApi() {
  vi.stubGlobal('fetch', vi.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input);
    const method = (init.method ?? 'GET').toUpperCase();
    calls.push(`${method} ${url.pathname}`);
    headers.push(new Headers(init.headers));
    const path = url.pathname;
    if (path === '/api/organizations/org-a' || path === '/api/organizations/org-b') {
      return Response.json({ id: path.split('/').pop(), name: 'Acme', current_user_role: 'admin', login_border_radius: '8' });
    }
    if (path.endsWith('/domains')) return Response.json([{ domain: 'acme.test', verified: true }]);
    if (path === '/api/agents/sync' || path === '/api/agents/') return Response.json(roster);
    if (path.startsWith('/api/agents/')) return Response.json({ ok: true });
    if (path === '/api/providers/models') return Response.json([{ canonical_id: 'claude-sonnet-5', model_id: 'claude-sonnet-5', provider: 'anthropic', name: 'Claude Sonnet 5' }]);
    if (path === '/api/providers/available') return Response.json([{ id: 'anthropic', name: 'Anthropic', type: 'anthropic', has_api_key: true, models: [] }]);
    if (path.startsWith('/api/iam/admin/')) return Response.json({});
    return Response.json({});
  }));
}

const count = (call: string) => calls.filter((c) => c === call).length;
/** The roster's own calls (choosing the chat's agent reads the workspaces besides). */
const agentCalls = () => calls.filter((c) => c.includes('/api/agents'));

beforeEach(() => {
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  useAuthStore.setState({ user: person('one'), csrfToken: 'csrf-one', isAuthenticated: true });
  clearResources();
  forgetAgentsSync();
  clearOrgBrandingCache();
  useAgentsStore.setState({ agents: [], agentsWorkspaceId: null, lastFetchedAt: {} });
  useModelsStore.setState({ models: [], lastFetchedAt: null });
  window.history.replaceState(null, '', '/');
  calls = [];
  headers = [];
  fakeApi();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('Organization settings share one read of the organization', () => {
  it('the layout, General, Branding and the shell ask once; a return asks nothing', async () => {
    const [layout, general, domains] = await Promise.all([
      readOrganization('org-a'),
      readOrganization('org-a'),
      readOrganizationDomains('org-a'),
      loadOrgBranding('org-a'),
    ]);
    expect((await layout.json()).current_user_role).toBe('admin');
    expect((await general.json()).name).toBe('Acme');
    expect(await domains.json()).toHaveLength(1);
    expect(calls).toEqual(['GET /api/organizations/org-a', 'GET /api/organizations/org-a/domains']);

    // Back on General a little later: nothing is asked again.
    await Promise.all([readOrganization('org-a'), readOrganizationDomains('org-a')]);
    expect(calls).toHaveLength(2);
  });

  it('a change under the organization is read again, another organization is kept', async () => {
    await Promise.all([readOrganization('org-a'), readOrganization('org-b')]);
    await authFetch('/api/organizations/org-a/domains', { method: 'POST', body: '{}' });
    await Promise.all([readOrganization('org-a'), readOrganization('org-b')]);
    expect(count('GET /api/organizations/org-a')).toBe(2);
    expect(count('GET /api/organizations/org-b')).toBe(1);

    window.dispatchEvent(new Event('org-branding-updated'));
    await readOrganization('org-b');
    expect(count('GET /api/organizations/org-b')).toBe(2);

    // Its record itself (a role can change with it) counts as an access change: all go.
    await authFetch('/api/organizations/org-a', { method: 'PATCH', body: '{}' });
    await readOrganization('org-b');
    expect(count('GET /api/organizations/org-b')).toBe(3);
  });

  it('an IAM change, another person or a refusal are never answered from memory', async () => {
    await readOrganization('org-a');
    await authFetch('/api/iam/admin/policies', { method: 'POST', body: '{}' });
    await readOrganization('org-a');
    expect(count('GET /api/organizations/org-a')).toBe(2);

    useAuthStore.setState({ user: person('two'), csrfToken: 'csrf-two', isAuthenticated: true });
    await readOrganization('org-a');
    expect(count('GET /api/organizations/org-a')).toBe(3);

    // Signed out: nothing is kept.
    useAuthStore.setState({ user: null, isAuthenticated: false });
    await readOrganization('org-a');
    await readOrganization('org-a');
    expect(count('GET /api/organizations/org-a')).toBe(5);
  });

  it('reads that decide nothing about the page keep the API live', async () => {
    window.history.replaceState(null, '', '/workspace/ws-1/settings/agents');
    await readOrganization('org-a');
    expect(headers[0].has(SETTINGS_CACHE_HEADER)).toBe(false);
  });
});

describe('Workspace Agents: one roster for the list, the detail and the store', () => {
  const visitList = async () => {
    await ensureAgentsSynced('ws-1', SETTINGS_RECONCILE_MS);
    await useAgentsStore.getState().fetchAgents('ws-1');
  };

  it('reconciles once, then the detail reads the same answer without a request', async () => {
    await Promise.all([visitList(), readAgentRoster('ws-1')]);
    expect(agentCalls()).toEqual(['POST /api/agents/sync']);
    expect(useAgentsStore.getState().agents.map((agent) => agent.id)).toEqual(['abi']);

    const detail = (await readAgentRoster('ws-1')) as typeof roster;
    // The service fields the store does not keep are the API's own.
    expect(detail[0].intents[0].intent_scope).toBe('workspace');
    expect(agentCalls()).toEqual(['POST /api/agents/sync']);

    // Back to the list and to the detail: nothing is asked.
    await visitList();
    await readAgentRoster('ws-1');
    expect(agentCalls()).toEqual(['POST /api/agents/sync']);
  });

  it('reconciles again once the last one is old, or after Reload', async () => {
    const now = Date.now();
    const clock = vi.spyOn(Date, 'now').mockReturnValue(now);
    await visitList();
    clock.mockReturnValue(now + SETTINGS_RECONCILE_MS);
    await visitList();
    expect(count('POST /api/agents/sync')).toBe(2);

    // The chat pane keeps its once-per-session rule.
    clock.mockReturnValue(now + 3 * SETTINGS_RECONCILE_MS);
    await ensureAgentsSynced('ws-1');
    expect(count('POST /api/agents/sync')).toBe(2);

    // Reload forgets every reconciliation and every kept answer.
    forgetAgentsSync();
    clearResources();
    await visitList();
    expect(count('POST /api/agents/sync')).toBe(3);
  });

  it('an agent change is read again by the detail, without reconciling', async () => {
    await visitList();
    await useAgentsStore.getState().updateAgent('abi', { name: 'Abi 2' });
    expect(useAgentsStore.getState().agents[0].name).toBe('Abi 2');
    await readAgentRoster('ws-1');
    expect(agentCalls()).toEqual(['POST /api/agents/sync', 'PATCH /api/agents/abi', 'GET /api/agents/']);
  });

  it('another person reconciles and reads their own roster', async () => {
    await visitList();
    useAuthStore.setState({ user: person('two'), csrfToken: 'csrf-two', isAuthenticated: true });
    await visitList();
    await readAgentRoster('ws-1');
    expect(agentCalls()).toEqual(['POST /api/agents/sync', 'POST /api/agents/sync']);
  });
});

describe('shared catalogs', () => {
  it('the store, Models settings and the providers ask each catalog once', async () => {
    await Promise.all([
      useModelsStore.getState().fetchModels(),
      readProviderModels(),
      readAvailableProviders(),
      useIntegrationsStore.getState().refreshProviders(),
    ]);
    expect(calls.sort()).toEqual(['GET /api/providers/available', 'GET /api/providers/models']);
    expect(useModelsStore.getState().models[0].name).toBe('Claude Sonnet 5');
    expect(useIntegrationsStore.getState().providers.map((provider) => provider.id)).toEqual(['anthropic']);

    // A model edited in Models settings: every consumer reads the catalog again.
    invalidateModelCatalog();
    await Promise.all([useModelsStore.getState().fetchModels(), readProviderModels()]);
    expect(count('GET /api/providers/models')).toBe(2);
  });
});

describe('the API settings cache follows the resource, not the open page', () => {
  it('a declared read keeps its policy on any page; an undeclared read follows the page', async () => {
    window.history.replaceState(null, '', '/workspace/ws-1/settings/agents');
    await authFetch('/api/skills?workspace_id=ws-1');
    await authFetch('/api/skills?workspace_id=ws-1', {}, { settingsCache: false });
    window.history.replaceState(null, '', '/workspace/ws-1/chat');
    await authFetch('/api/skills?workspace_id=ws-1', {}, { settingsCache: true });
    await authFetch('/api/skills?workspace_id=ws-1');
    await authFetch('/api/skills', { method: 'POST', body: '{}' }, { settingsCache: true });
    expect(headers.map((sent) => sent.get(SETTINGS_CACHE_HEADER))).toEqual(['1', null, '1', null, null]);
  });
});
