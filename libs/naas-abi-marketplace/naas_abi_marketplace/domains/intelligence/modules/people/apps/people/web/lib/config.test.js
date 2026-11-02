import assert from "node:assert/strict";
import { afterEach, it } from "node:test";

const originals = { document: globalThis.document, window: globalThis.window, fetch: globalThis.fetch };
afterEach(() => {
  for (const [name, value] of Object.entries(originals)) {
    if (value === undefined) delete globalThis[name];
    else globalThis[name] = value;
  }
});

async function configuration(id) {
  globalThis.document = { querySelector: () => null, documentElement: { dataset: {} } };
  globalThis.window = {
    location: { pathname: "/", search: "" },
    localStorage: { getItem: () => null },
  };
  return import(`./config.js?config-test=${id}`);
}

it("boot and shell share one in-flight config request and its result", async () => {
  const { loadAppConfig } = await configuration("shared");
  let resolve;
  let calls = 0;
  const response = new Promise((done) => { resolve = done; });
  globalThis.fetch = () => { calls += 1; return response; };
  const boot = loadAppConfig();
  const shell = loadAppConfig();
  assert.equal(calls, 1);
  resolve({ ok: true, json: async () => ({ brand: { name: "Directory" } }) });
  assert.deepEqual(await boot, await shell);
  assert.deepEqual(await loadAppConfig(), { brand: { name: "Directory" } });
  assert.equal(calls, 1);
});

it("retries config after a failed request instead of caching the failure", async () => {
  const { loadAppConfig } = await configuration("retry");
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return calls === 1 ? { ok: false, status: 503 } : { ok: true, json: async () => ({}) };
  };
  await assert.rejects(loadAppConfig(), /config → 503/);
  assert.deepEqual(await loadAppConfig(), {});
  assert.equal(calls, 2);
});

it("keeps in-flight configuration scoped to its Nexus workspace", async () => {
  const { loadAppConfig } = await configuration("workspace");
  window.location.pathname = "/app-html/example/people/web/index.html";
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => ({ url }) };
  };
  window.location.search = "?workspace=one";
  const one = loadAppConfig();
  window.location.search = "?workspace=two";
  const two = loadAppConfig();
  assert.notDeepEqual(await one, await two);
  window.location.search = "?workspace=one";
  assert.deepEqual(await loadAppConfig(), await one);
  assert.deepEqual(calls, ["/api/people/config?workspace_id=one", "/api/people/config?workspace_id=two"]);
});
