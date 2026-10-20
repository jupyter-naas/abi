import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { fitTabs } from "./tab-overflow.js";

describe("fitTabs", () => {
  it("keeps every tab when they all fit, with no room set aside for 'more'", () => {
    assert.deepEqual(fitTabs([50, 50, 50], 150, 60), [0, 1, 2]);
  });

  it("keeps the tabs that fit beside the 'more' tab, in order", () => {
    assert.deepEqual(fitTabs([50, 50, 50, 50], 170, 60), [0, 1]);
  });

  it("keeps a selected tab that already fits where it is", () => {
    assert.deepEqual(fitTabs([50, 50, 50, 50], 170, 60, 1), [0, 1]);
  });

  it("brings a hidden selected tab into the row in place of the last ones", () => {
    assert.deepEqual(fitTabs([50, 50, 50, 50], 170, 60, 3), [0, 3]);
  });

  it("drops as many tabs as a wide selected tab needs", () => {
    assert.deepEqual(fitTabs([50, 50, 50, 100], 170, 60, 3), [3]);
  });

  it("keeps the selected tab even when nothing else fits", () => {
    assert.deepEqual(fitTabs([50, 50, 200], 170, 60, 2), [2]);
  });
});
