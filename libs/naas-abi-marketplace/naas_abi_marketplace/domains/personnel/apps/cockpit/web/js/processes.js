/**
 * BFO 7-buckets process presenter (schema from example/BFO_7B.html).
 */

const BUCKET_ORDER = [
  "what",
  "when",
  "who",
  "where",
  "how_to_know",
  "how_it_is",
  "why",
];

const BUCKET_WORD = {
  what: "WHAT",
  when: "WHEN",
  who: "WHO",
  where: "WHERE",
  how_to_know: "HOW-TO-\nKNOW",
  how_it_is: "HOW-IT-IS",
  why: "WHY",
};

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function multilabel(text, x, y, fill, size = 12) {
  const lines = String(text || "").split("\n");
  const start = y - ((lines.length - 1) * 14) / 2;
  return lines
    .map(
      (line, i) =>
        `<text x="${x}" y="${start + i * 14}" fill="${fill}" font-size="${size}" font-weight="700" letter-spacing="0.5" text-anchor="middle">${esc(line)}</text>`
    )
    .join("");
}

function bfoSlideSvg(proc) {
  const b = proc.buckets || {};
  const node = (key, cx, cy, accent) => {
    const meta = b[key] || {};
    const stroke = accent ? "#34d399" : "#3a3a3a";
    const fill = accent ? "#10291f" : "#141414";
    const wordFill = accent ? "#34d399" : "#f8fafc";
    const word = BUCKET_WORD[key];
    // Schema: class/process label above the circle, bucket word inside.
    const above = meta.label || meta.bfo || "";
    const aboveLines =
      above.length > 18
        ? above.split(/[·•]/).map((s) => s.trim()).filter(Boolean).slice(0, 3)
        : [above];
    const aboveY = cy - 62 - (aboveLines.length - 1) * 13;
    return `
      <g id="node-${key}">
        ${aboveLines
          .map(
            (line, i) =>
              `<text x="${cx}" y="${aboveY + i * 13}" fill="#f8fafc" font-size="12" font-weight="500" text-anchor="middle">${esc(line)}</text>`
          )
          .join("")}
        <circle cx="${cx}" cy="${cy}" r="52" fill="${fill}" stroke="${stroke}" stroke-width="1.8"></circle>
        ${multilabel(word, cx, cy + (key === "how_to_know" ? 0 : 5), wordFill, key === "how_to_know" ? 13 : 15)}
        ${key === "where" ? `<line x1="${cx - 29}" y1="${cy + 11}" x2="${cx + 29}" y2="${cy + 11}" stroke="${wordFill}" stroke-width="1.2"></line>` : ""}
      </g>`;
  };

  return `
<svg class="slide-canvas" viewBox="0 0 1280 720" width="1280" height="720" role="img"
  aria-label="${esc(proc.title)} — BFO 7 buckets"
  font-family="Roboto, ui-sans-serif, system-ui, sans-serif">
  <title>${esc(proc.title)}</title>
  <defs>
    <marker id="arrow-bfo-${esc(proc.id)}" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#34d399"></path></marker>
    <marker id="arrow-bfo-muted-${esc(proc.id)}" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#6b7280"></path></marker>
  </defs>
  <rect width="1280" height="720" fill="#000000"></rect>
  <g id="realms">
    <rect x="0" y="130" width="1280" height="170" fill="#0d0d0d"></rect>
    <rect x="0" y="300" width="1280" height="360" fill="#0a0a0a"></rect>
    <line x1="0" y1="300" x2="1280" y2="300" stroke="#242424" stroke-width="1"></line>
    <text x="40" y="152" font-size="12" fill="#4b5563" font-weight="600" letter-spacing="2">OCCURRENTS</text>
    <text x="40" y="322" font-size="12" fill="#4b5563" font-weight="600" letter-spacing="2">CONTINUANTS</text>
  </g>
  <g id="arrows" fill="none" stroke-width="1.5">
    <path d="M652,215 H1094" stroke="#34d399" marker-end="url(#arrow-bfo-${esc(proc.id)})"></path>
    <path d="M553,237 L189,407" stroke="#34d399" marker-end="url(#arrow-bfo-${esc(proc.id)})"></path>
    <path d="M572,259 L490,385" stroke="#34d399" marker-end="url(#arrow-bfo-${esc(proc.id)})"></path>
    <path d="M610,266 L630,376" stroke="#34d399" marker-end="url(#arrow-bfo-${esc(proc.id)})"></path>
    <path d="M642,246 L851,398" stroke="#34d399" marker-end="url(#arrow-bfo-${esc(proc.id)})"></path>
    <path d="M648,234 L1100,410" stroke="#34d399" marker-end="url(#arrow-bfo-${esc(proc.id)})"></path>
    <path d="M192,430 H404" stroke="#6b7280" marker-end="url(#arrow-bfo-muted-${esc(proc.id)})"></path>
    <path d="M843,430 H695" stroke="#6b7280" marker-end="url(#arrow-bfo-muted-${esc(proc.id)})"></path>
    <path d="M124,478 V560 H620 V481" stroke="#6b7280" marker-end="url(#arrow-bfo-muted-${esc(proc.id)})"></path>
    <path d="M140,482 V590 H880 V483" stroke="#6b7280" marker-end="url(#arrow-bfo-muted-${esc(proc.id)})"></path>
    <path d="M156,478 V620 H1150 V485" stroke="#6b7280" marker-end="url(#arrow-bfo-muted-${esc(proc.id)})"></path>
    <path d="M1122,474 V545 H660 V481" stroke="#6b7280" marker-end="url(#arrow-bfo-muted-${esc(proc.id)})"></path>
  </g>
  <g id="arrow-labels" font-size="12" fill="#9ca3af" font-weight="500">
    <text x="873" y="207" text-anchor="middle">occupies temporal region</text>
    <text x="330" y="305" text-anchor="middle">has participant</text>
    <text x="478" y="346" text-anchor="middle">occurs in</text>
    <text x="644" y="328" text-anchor="start">concretizes</text>
    <text x="795" y="350" text-anchor="start">has participant</text>
    <text x="910" y="318" text-anchor="middle">realizes</text>
    <text x="296" y="422" text-anchor="middle">located in</text>
    <text x="770" y="422" text-anchor="middle">concretizes</text>
    <rect x="344" y="551" width="92" height="16" fill="#0a0a0a"></rect>
    <text x="390" y="564" text-anchor="middle">is carrier of</text>
    <rect x="464" y="581" width="72" height="16" fill="#0a0a0a"></rect>
    <text x="500" y="594" text-anchor="middle">bearer of</text>
    <rect x="836" y="611" width="128" height="16" fill="#0a0a0a"></rect>
    <text x="900" y="624" text-anchor="middle">material basis of*</text>
    <rect x="947" y="537" width="86" height="16" fill="#0a0a0a"></rect>
    <text x="990" y="550" text-anchor="middle">concretizes</text>
  </g>
  <g id="nodes" text-anchor="middle">
    ${node("what", 600, 215, true)}
    ${node("when", 1150, 215, false)}
    ${node("who", 140, 430, false)}
    ${node("where", 460, 430, false)}
    ${node("how_to_know", 640, 430, false)}
    ${node("how_it_is", 895, 430, false)}
    ${node("why", 1150, 430, false)}
  </g>
  <g id="footer" font-size="13" fill="#4b5563">
    <text x="40" y="692">Cockpit · Processes</text>
    <text x="1240" y="692" text-anchor="end">${esc(proc.status)}</text>
  </g>
</svg>`;
}

function renderRestrictions(list) {
  if (!list?.length) return `<p class="empty">No restrictions listed.</p>`;
  return `
    <table class="onto-restrictions">
      <thead>
        <tr>
          <th>On</th>
          <th>Property</th>
          <th>someValuesFrom</th>
          <th>Definition / example</th>
        </tr>
      </thead>
      <tbody>
        ${list
          .map(
            (r) => `<tr>
            <td><code>${esc(r.on)}</code></td>
            <td>
              <strong>${esc(r.property)}</strong>
              <div class="iri">${esc(r.property_iri || "")}</div>
            </td>
            <td><code>${esc(r.someValuesFrom)}</code></td>
            <td>
              <div>${esc(r.definition || "")}</div>
              ${r.example ? `<div class="ex">Ex: ${esc(r.example)}</div>` : ""}
            </td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function renderBucketCards(proc) {
  return `<div class="onto-buckets">${BUCKET_ORDER.map((key) => {
    const meta = proc.buckets?.[key] || {};
    return `<div class="onto-bucket${key === "what" ? " accent" : ""}">
      <span class="onto-bucket-word">${esc(BUCKET_WORD[key].replace("\n", " "))}</span>
      <strong>${esc(meta.label || "—")}</strong>
      <small>${esc(meta.bfo || "")}</small>
      <code>${esc(meta.class || "")}</code>
    </div>`;
  }).join("")}</div>`;
}

export function mountProcessesPage(el, data) {
  const processes = data.processes || [];
  let activeId = processes[0]?.id;

  function paint() {
    const proc = processes.find((p) => p.id === activeId) || processes[0];
    if (!proc) {
      el.innerHTML = `<p class="banner">No processes documented.</p>`;
      return;
    }
    el.innerHTML = `
      <div class="onto-picker" role="tablist" aria-label="Processes">
        ${processes
          .map(
            (p) => `<button type="button" role="tab" data-proc="${esc(p.id)}"
              class="${p.id === proc.id ? "active" : ""}"
              aria-selected="${p.id === proc.id}">
              <span class="onto-status ${esc(p.status)}">${esc(p.status)}</span>
              ${esc(p.label)}
              <small>${(p.pages || []).join(" · ")}</small>
            </button>`
          )
          .join("")}
      </div>

      <div class="bfo-stage">
        <div class="slide-frame" data-slide-frame>
          <figure>
            <p class="ly kicker f-roboto">${esc(proc.kicker)}</p>
            <h2 class="ly f-lora">${esc(proc.title)}</h2>
            <p class="ly sub f-roboto">${esc(proc.subtitle)}</p>
            ${bfoSlideSvg(proc)}
            <span class="naas-logo" aria-hidden="true">naas</span>
          </figure>
        </div>
      </div>

      <div class="onto-def panel">
        <h2>Definition</h2>
        <p class="onto-def-text">${esc(proc.definition)}</p>
        <p class="onto-ex"><strong>Example.</strong> ${esc(proc.example)}</p>
        ${proc.comment ? `<p class="onto-comment">${esc(proc.comment)}</p>` : ""}
        <p class="onto-meta"><code>${esc(proc.source || "")}</code>
          ${proc.iri ? ` · <code>${esc(proc.iri)}</code>` : ""}</p>
      </div>

      <div class="panel" style="margin-bottom:1rem">
        <h2>Seven buckets (this process)</h2>
        ${renderBucketCards(proc)}
      </div>

      <div class="panel">
        <h2>Restrictions</h2>
        ${renderRestrictions(proc.restrictions)}
      </div>

      <div class="agent-q"><strong>Ask PersonnelAgent:</strong> “Explain BirthRegistrationProcess.” · “What is the difference between EmployeeRole and JobPosition?”</div>
    `;

    el.querySelectorAll("[data-proc]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeId = btn.dataset.proc;
        paint();
      });
    });

    const frame = el.querySelector("[data-slide-frame]");
    const figure = frame?.querySelector("figure");
    if (frame && figure) {
      const scale = () => {
        figure.style.transform = `scale(${frame.clientWidth / 1280})`;
      };
      scale();
      if (el._ontoResize) window.removeEventListener("resize", el._ontoResize);
      el._ontoResize = scale;
      window.addEventListener("resize", scale);
    }
  }

  paint();
  return () => {
    if (el._ontoResize) window.removeEventListener("resize", el._ontoResize);
  };
}
