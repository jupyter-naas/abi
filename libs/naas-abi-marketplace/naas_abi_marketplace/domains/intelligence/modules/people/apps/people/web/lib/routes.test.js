import assert from "node:assert/strict";
import { afterEach, it } from "node:test";

import { syncLandingHash } from "./routes.js";

const originalWindow = globalThis.window;
afterEach(() => {
  if (originalWindow === undefined) delete globalThis.window;
  else globalThis.window = originalWindow;
});

const config = {
  app: {
    default_page: "results",
    pages: [{ page_id: "results", url: "search" }],
  },
};

function browserAt(hash) {
  const replacements = [];
  const state = { app: "people" };
  globalThis.window = {
    location: { hash, pathname: "/people/web/index.html", search: "?workspace=one" },
    history: { state, replaceState: (...args) => replacements.push(args) },
  };
  return { replacements, state };
}

it("sets the landing URL through history so startup does not dispatch another render", () => {
  const { replacements, state } = browserAt("");
  syncLandingHash(config);
  assert.deepEqual(replacements, [[state, "", "/people/web/index.html?workspace=one#/search"]]);
});

it("preserves an explicit deep link", () => {
  const { replacements } = browserAt("#/search?q=skills&page=2");
  syncLandingHash(config);
  assert.equal(replacements.length, 0);
});

it("leaves the canonical URL alone", () => {
  const { replacements } = browserAt("#/search");
  syncLandingHash(config);
  assert.equal(replacements.length, 0);
});

it("preserves the configured default display", () => {
  const { replacements } = browserAt("#/");
  syncLandingHash({ app: { ...config.app, default_results_view: "network" } });
  assert.equal(replacements[0][2], "/people/web/index.html?workspace=one#/search?display=network");
});
