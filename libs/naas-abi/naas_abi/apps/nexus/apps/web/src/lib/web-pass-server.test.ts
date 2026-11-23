import { afterEach, describe, expect, it, vi } from 'vitest';

import { checkWebPass, forgetWebPasses } from './web-pass-server';

afterEach(() => {
  forgetWebPasses();
  vi.unstubAllGlobals();
});

describe('web pass check', () => {
  it('keeps a refusal only when the API refused the pass', async () => {
    const answers = [
      new Response('busy', { status: 503 }),
      Response.json({ user_id: 'usr_ada', expires_in: 600 }),
    ];
    const fetchMock = vi.fn(async () => answers.shift()!);
    vi.stubGlobal('fetch', fetchMock);
    // An API that cannot answer names nobody, and is asked again next time.
    expect(await checkWebPass('abi_gk_pass_one')).toBeNull();
    expect(await checkWebPass('abi_gk_pass_one')).toEqual({ userId: 'usr_ada', expiresIn: 600 });

    const refused = vi.fn(async () => Response.json({ detail: 'Not signed in' }, { status: 401 }));
    vi.stubGlobal('fetch', refused);
    expect(await checkWebPass('abi_gk_pass_two')).toBeNull();
    expect(await checkWebPass('abi_gk_pass_two')).toBeNull();
    expect(refused).toHaveBeenCalledTimes(1);
  });

  it('keeps anything not shaped like a pass from reaching the API', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    for (const value of [null, '', 'true', 'abi_pk_key', 'abi_gk_a b', `abi_gk_${'x'.repeat(600)}`]) {
      expect(await checkWebPass(value)).toBeNull();
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
