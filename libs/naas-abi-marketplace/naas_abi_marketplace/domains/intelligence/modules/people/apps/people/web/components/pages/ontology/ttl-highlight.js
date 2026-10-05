import { escapeHtml } from "../../../lib/dom.js";

// One pass over the raw Turtle, first matching alternative wins. Running one
// regex per class over the growing HTML instead matched the class names of the
// spans already inserted and broke the markup. IRIs are tokens of their own so
// the `#` in `<http://www.w3.org/2002/07/owl#>` is not read as a comment.
const TOKENS = [
  ["ttl-string", /"""[\s\S]*?"""/],
  ["ttl-string", /"(?:[^"\\\n]|\\.)*"/],
  ["ttl-prefix", /@prefix\b[^\n]*/],
  ["ttl-iri", /<[^>\s]*>/],
  ["ttl-comment", /#[^\n]*/],
  ["ttl-type", /\^\^[A-Za-z][\w-]*:\w+/],
  ["ttl-kw", /\ba owl:(?:Class|ObjectProperty|DatatypeProperty|Ontology|Restriction)\b/],
  ["ttl-pred", /\b(?:rdfs|owl|skos):\w+\b/],
  ["ttl-qname", /\b[A-Za-z][\w-]*:/],
];

const PATTERN = new RegExp(TOKENS.map(([, re]) => `(${re.source})`).join("|"), "g");

export function highlightTurtle(text) {
  const source = String(text ?? "");
  let html = "";
  let last = 0;
  for (const match of source.matchAll(PATTERN)) {
    const group = match.slice(1).findIndex((value) => value !== undefined);
    html += escapeHtml(source.slice(last, match.index));
    html += `<span class="${TOKENS[group][0]}">${escapeHtml(match[0])}</span>`;
    last = match.index + match[0].length;
  }
  return html + escapeHtml(source.slice(last));
}
