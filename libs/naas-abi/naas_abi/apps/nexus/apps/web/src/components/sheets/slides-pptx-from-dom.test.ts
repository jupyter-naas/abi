import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { SHEETS_STAGE_HEIGHT, SHEETS_STAGE_WIDTH } from './sheets-preview-fit';
import {
  planSheetsPptxFromHtml,
  SHEETS_PPTX_FROM_DOM_FINGERPRINT,
  SHEETS_PPTX_FROM_DOM_FN,
  SHEETS_PPTX_FROM_DOM_SCRIPT,
  SHEETS_PPTX_FROM_DOM_SCRIPT_ID,
  SHEETS_PPTX_HEIGHT_IN,
  SHEETS_PPTX_STAGE_HEIGHT_PX,
  SHEETS_PPTX_STAGE_WIDTH_PX,
  SHEETS_PPTX_WIDTH_IN,
} from './sheets-pptx-from-dom';

const FIXTURE = `<!doctype html>
<html><head><style>
:root {
  --panel: #ffffff;
  --ink: #1a1a1a;
  --muted: #6b6b6b;
  --accent: #1a1a1a;
  --card: #fafaf8;
}
</style></head>
<body>
<main class="workbook">
<section id="slide-cover" class="slide cover">
  <h1>Q3 Review</h1>
  <p class="subtitle">Exec team readout</p>
  <div class="hook">30 min</div>
</section>
<section class="slide">
  <div class="eyebrow">Agenda</div>
  <h1>What we will cover</h1>
  <div class="agenda-row"><h2>Context</h2><p>Why now</p></div>
</section>
<section class="slide">
  <div class="eyebrow">Context</div>
  <h1>Shared problem</h1>
  <div class="card"><h2>Current state</h2><ul><li>Gap one</li></ul></div>
</section>
</main>
<script>const FOOTER_TXT = "Workbook Title"; function buildPptx(){ /* seed strings */ }</script>
</body></html>`;

function seedHtml(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  const path = resolve(
    here,
    '../../../../../assets/sheets/templates/grid-light-v1.html',
  );
  return readFileSync(path, 'utf8');
}

describe('planSheetsPptxFromHtml', () => {
  it('uses the 1280x720 / 13.333x7.5 stage', () => {
    const plan = planSheetsPptxFromHtml(FIXTURE);
    expect(plan.stage.widthPx).toBe(SHEETS_STAGE_WIDTH);
    expect(plan.stage.heightPx).toBe(SHEETS_STAGE_HEIGHT);
    expect(plan.stage.widthPx).toBe(SHEETS_PPTX_STAGE_WIDTH_PX);
    expect(plan.stage.heightPx).toBe(SHEETS_PPTX_STAGE_HEIGHT_PX);
    expect(plan.stage.widthIn).toBe(SHEETS_PPTX_WIDTH_IN);
    expect(plan.stage.heightIn).toBe(SHEETS_PPTX_HEIGHT_IN);
  });

  it('reads live HTML: slide count, cover h1, colors, not script strings', () => {
    const plan = planSheetsPptxFromHtml(FIXTURE);
    expect(plan.slideCount).toBe(3);
    expect(plan.coverH1).toBe('Q3 Review');
    expect(plan.coverSubtitle).toBe('Exec team readout');
    expect(plan.colors.panel).toBe('ffffff');
    expect(plan.colors.ink).toBe('1a1a1a');
    expect(plan.sheets.map((s) => s.kind)).toEqual(['cover', 'agenda', 'cards']);
    expect(plan.sheets[0].texts).toContain('Q3 Review');
    expect(plan.coverH1).not.toBe('Workbook Title');
  });

  it('picks up an agent cover h1 edit', () => {
    const edited = FIXTURE.replace('<h1>Q3 Review</h1>', '<h1>Q3 Review for execs</h1>');
    const plan = planSheetsPptxFromHtml(edited);
    expect(plan.coverH1).toBe('Q3 Review for execs');
    expect(plan.slideCount).toBe(3);
  });

  it('plans every section when the agent adds sheets (not a 4-slide script)', () => {
    const extra = FIXTURE.replace(
      '</main>',
      `<section class="slide"><h1>Roadmap</h1></section>
<section class="slide"><h1>Next</h1></section></main>`,
    );
    const plan = planSheetsPptxFromHtml(extra);
    expect(plan.slideCount).toBe(5);
    expect(plan.sheets[3].title).toBe('Roadmap');
    expect(plan.sheets[4].title).toBe('Next');
  });
});

describe('seed template contract', () => {
  it('plans all Minimal Light sheets and the cover h1 from HTML', () => {
    const html = seedHtml();
    const plan = planSheetsPptxFromHtml(html);
    expect(plan.slideCount).toBe(10);
    expect(plan.coverH1).toBe('Workbook Title');
    expect(plan.colors.panel).toBe('ffffff');
    expect(plan.sheets[0].kind).toBe('cover');
    expect(plan.sheets.some((s) => s.kind === 'divider')).toBe(true);
    const edited = html.replace(
      '<h1>Workbook Title</h1>',
      '<h1>Board update</h1>',
    );
    expect(planSheetsPptxFromHtml(edited).coverH1).toBe('Board update');
  });

  it('ships the DOM walker instead of a 4-slide hardcoded export', () => {
    const html = seedHtml();
    expect(html).toContain(SHEETS_PPTX_FROM_DOM_FINGERPRINT);
    expect(html).toContain('querySelectorAll("main.workbook > section.slide');
    expect(html).not.toContain('[["1","Context"],["2","Approach"]');
    expect(html).not.toContain('txt(s, "Workbook Title", 56, 380');
  });
});

describe('injected PPTX-from-DOM script', () => {
  it('overrides window.buildPptx from the live DOM', () => {
    expect(SHEETS_PPTX_FROM_DOM_SCRIPT).toContain(SHEETS_PPTX_FROM_DOM_SCRIPT_ID);
    expect(SHEETS_PPTX_FROM_DOM_SCRIPT).toContain(SHEETS_PPTX_FROM_DOM_FINGERPRINT);
    expect(SHEETS_PPTX_FROM_DOM_SCRIPT).toContain('window.buildPptx = buildPptx');
    expect(SHEETS_PPTX_FROM_DOM_FN).toContain('querySelectorAll("main.workbook > section.slide');
    expect(SHEETS_PPTX_FROM_DOM_FN).toContain('prop("--panel"');
    expect(SHEETS_PPTX_FROM_DOM_FN).toContain('classList.contains("cover")');
  });
});
