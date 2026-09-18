import { escapeHtml } from "../../../lib/dom.js";

const RULES = [
  { re: /^(@prefix\b[^\n]*)/gm, cls: "ttl-prefix" },
  { re: /(\b[a-zA-Z][\w-]*:)/g, cls: "ttl-qname" },
  { re: /("(?:[^"\\]|\\.)*")/g, cls: "ttl-string" },
  { re: /(\^\^xsd:[\w]+)/g, cls: "ttl-type" },
  { re: /(\ba owl:(?:Class|ObjectProperty|DatatypeProperty|Ontology|Restriction)\b)/g, cls: "ttl-kw" },
  { re: /(\b(?:rdfs|owl|skos):[\w]+\b)/g, cls: "ttl-pred" },
  { re: /(#[^\n]*)/g, cls: "ttl-comment" },
];

export function highlightTurtle(text) {
  let html = escapeHtml(text);
  for (const rule of RULES) {
    html = html.replace(rule.re, (match) => `<span class="${rule.cls}">${match}</span>`);
  }
  return html;
}
