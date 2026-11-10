import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { connectionsLabel, personOfQuery, resultsState } from "./results-state.js";

const params = (text) => new URLSearchParams(text);

describe("resultsState", () => {
  it("opens the People tab as a list by default", () => {
    assert.deepEqual(resultsState(params("q=axa")), {
      query: "axa",
      facet: "",
      view: "",
      display: "",
      person: "",
      page: 1,
    });
  });

  it("reads the tab, the display and the person", () => {
    const state = resultsState(params("q=x&facet=France&view=connections&display=network&person=li_jane"));
    assert.equal(state.view, "connections");
    assert.equal(state.display, "network");
    assert.equal(state.person, "li_jane");
    assert.equal(state.facet, "France");
  });

  it("opens an old Network tab link as the People tab drawn as a network", () => {
    const state = resultsState(params("q=edf&view=network"));
    assert.equal(state.view, "");
    assert.equal(state.display, "network");
  });

  it("uses the configured default display only when the URL says nothing", () => {
    assert.equal(resultsState(params("q=x"), "network").display, "network");
    assert.equal(resultsState(params("q=x&display="), "network").display, "");
  });

  it("ignores values it does not know", () => {
    const state = resultsState(params("view=bogus&display=3d&page=-2"));
    assert.equal(state.view, "");
    assert.equal(state.display, "");
    assert.equal(state.page, 1);
  });
});

describe("personOfQuery", () => {
  const results = [
    { slug: "a", full_name: "Jérôme Durand" },
    { slug: "b", full_name: "Jane Doe" },
    { slug: "c", full_name: "Jane  Doe" },
  ];

  it("is the one result whose name is the query, accents and case aside", () => {
    assert.equal(personOfQuery(results, "jerome durand").slug, "a");
  });

  it("is nobody when two people carry the name", () => {
    assert.equal(personOfQuery(results, "Jane Doe"), null);
  });

  it("is nobody for a query that names no one", () => {
    assert.equal(personOfQuery(results, "risk"), null);
    assert.equal(personOfQuery(results, ""), null);
  });
});

describe("connectionsLabel", () => {
  it("says nothing for none, and counts otherwise", () => {
    assert.equal(connectionsLabel(0), "");
    assert.equal(connectionsLabel(1), "1 connection");
    assert.equal(connectionsLabel(12), "12 connections");
  });
});
