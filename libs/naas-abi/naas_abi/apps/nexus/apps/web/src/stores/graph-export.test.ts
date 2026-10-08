import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.fn();

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));
vi.mock('@/stores/auth', () => ({ authFetch: (...args: unknown[]) => authFetch(...args) }));
vi.mock('@/lib/graph-export-records', async () => ({
  ...(await vi.importActual<object>('@/lib/graph-export-records')),
  loadExportRecords: () => [],
  saveExportRecords: () => undefined,
}));

const { useGraphExportStore } = await import('./graph-export');

function streamedExport(counts: { triples: string; individuals: string }) {
  let pulls = 0;
  const cancel = vi.fn();
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      pulls += 1;
      if (pulls > 1000) controller.close();
      else controller.enqueue(new TextEncoder().encode('<urn:s> <urn:p> <urn:o> .\n'));
    },
    cancel,
  });
  const response = new Response(body, {
    headers: {
      'X-Triple-Count': counts.triples,
      'X-Named-Individual-Count': counts.individuals,
    },
  });
  return { response, cancel, pulls: () => pulls };
}

describe('graph export jobs', () => {
  beforeEach(() => {
    authFetch.mockReset();
    useGraphExportStore.setState({ recordsByWorkspace: {}, toasts: [], isExportPageActive: true });
  });

  it('reads the counts from the headers and stops the streamed body', async () => {
    const exported = streamedExport({ triples: '42', individuals: '7' });
    authFetch.mockResolvedValueOnce(exported.response);

    const id = useGraphExportStore
      .getState()
      .startExport('ws-1', { uri: 'urn:graph:a', label: 'A' }, 'nt');

    await vi.waitFor(() => {
      const record = useGraphExportStore.getState().recordsByWorkspace['ws-1'][0];
      expect(record).toMatchObject({ id, status: 'ready', tripleCount: 42 });
    });
    expect(exported.cancel).toHaveBeenCalledOnce();
    expect(exported.pulls()).toBeLessThan(3); // never read to the end
    expect(authFetch).toHaveBeenCalledOnce();
    expect(String(authFetch.mock.calls[0][0])).toContain('format=nt');
  });

  it('marks the record failed when the export is refused', async () => {
    authFetch.mockResolvedValueOnce(new Response(null, { status: 403 }));

    useGraphExportStore.getState().startExport('ws-1', { uri: 'urn:graph:b', label: 'B' }, 'ttl');

    await vi.waitFor(() => {
      const record = useGraphExportStore.getState().recordsByWorkspace['ws-1'][0];
      expect(record).toMatchObject({ status: 'error', error: 'Export failed (403)' });
    });
  });
});
