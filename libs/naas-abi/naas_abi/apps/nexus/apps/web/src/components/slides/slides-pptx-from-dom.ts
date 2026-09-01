/**
 * HTML is the live Slides source. PPTX is a 1280x720 reconstruction of the
 * current `.slide` DOM (pptxgenjs). Preview is the HTML stage.
 *
 * pptxgenjs cannot match CSS pixel-for-pixel (web fonts, wrapping,
 * letter-spacing). Export must still carry the same slide count, cover h1,
 * body copy, layout regions, and theme colors.
 */

export const SLIDES_PPTX_FROM_DOM_SCRIPT_ID = 'nexus-slides-pptx-from-dom';
export const SLIDES_PPTX_FROM_DOM_FINGERPRINT = 'NEXUS_SLIDES_PPTX_FROM_DOM_V1';

export const SLIDES_PPTX_STAGE_WIDTH_PX = 1280;
export const SLIDES_PPTX_STAGE_HEIGHT_PX = 720;
export const SLIDES_PPTX_DPI = 96;
export const SLIDES_PPTX_WIDTH_IN = 13.333;
export const SLIDES_PPTX_HEIGHT_IN = 7.5;

export type SlidesPptxSlideKind =
  | 'cover'
  | 'divider'
  | 'agenda'
  | 'cards'
  | 'steps'
  | 'content';

export type SlidesPptxPlanSlide = {
  kind: SlidesPptxSlideKind;
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  hook?: string;
  footer?: string;
  texts: string[];
};

export type SlidesPptxPlan = {
  stage: {
    widthPx: number;
    heightPx: number;
    widthIn: number;
    heightIn: number;
    dpi: number;
  };
  colors: {
    panel: string;
    ink: string;
    muted: string;
    accent: string;
    card: string;
  };
  coverH1: string | null;
  coverSubtitle: string | null;
  slideCount: number;
  slides: SlidesPptxPlanSlide[];
};

const SECTION_RE =
  /<section\b[^>]*\bclass=["'][^"']*\bslide\b[^"']*["'][^>]*>[\s\S]*?<\/section>/gi;
const ROOT_RE = /:root\s*\{([\s\S]*?)\}/;
const CSS_VAR_RE = /--([a-z0-9-]+)\s*:\s*([^;]+);/gi;
const TAG_RE = /<[^>]+>/g;

function stripTags(html: string): string {
  return html.replace(TAG_RE, ' ').replace(/\s+/g, ' ').trim();
}

function unescapeHtml(value: string): string {
  return value
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&mdash;/gi, '-')
    .replace(/&ndash;/gi, '-')
    .replace(/&#0*8212;/g, '-')
    .replace(/&#x0*2014;/gi, '-')
    .replace(/&#0*8211;/g, '-')
    .replace(/&#x0*2013;/gi, '-')
    .replace(/&#(\d+);/g, (_, n: string) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n: string) =>
      String.fromCodePoint(parseInt(n, 16)),
    );
}

function inner(html: string, tag: string, className?: string): string | null {
  const attr = className
    ? `\\bclass=["'][^"']*\\b${className}\\b[^"']*["']`
    : '';
  const re = new RegExp(
    `<${tag}\\b[^>]*${attr}[^>]*>([\\s\\S]*?)</${tag}>`,
    'i',
  );
  const match = re.exec(html);
  if (!match) return null;
  const text = unescapeHtml(stripTags(match[1]));
  return text || null;
}

function allInner(html: string, tag: string, className?: string): string[] {
  const attr = className
    ? `\\bclass=["'][^"']*\\b${className}\\b[^"']*["']`
    : '';
  const re = new RegExp(
    `<${tag}\\b[^>]*${attr}[^>]*>([\\s\\S]*?)</${tag}>`,
    'gi',
  );
  const out: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = re.exec(html))) {
    const text = unescapeHtml(stripTags(match[1]));
    if (text) out.push(text);
  }
  return out;
}

function hasClass(openTag: string, name: string): boolean {
  const classMatch = openTag.match(/\bclass=["']([^"']+)["']/i);
  if (!classMatch) return false;
  return classMatch[1].split(/\s+/).includes(name);
}

function normalizeHex(raw: string | undefined, fallback: string): string {
  const value = (raw || fallback).trim();
  const hex = value.match(/#([0-9a-fA-F]{6})/);
  if (hex) return hex[1].toLowerCase();
  const short = value.match(/#([0-9a-fA-F]{3})\b/);
  if (short) {
    const [r, g, b] = short[1];
    return `${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  return fallback.replace('#', '').toLowerCase();
}

function cssVars(html: string): Record<string, string> {
  const block = ROOT_RE.exec(html);
  if (!block) return {};
  const vars: Record<string, string> = {};
  let match: RegExpExecArray | null;
  const re = new RegExp(CSS_VAR_RE.source, 'gi');
  while ((match = re.exec(block[1]))) {
    vars[match[1]] = match[2].trim();
  }
  return vars;
}

function classify(section: string): SlidesPptxSlideKind {
  const open = section.match(/^<section\b[^>]*>/i)?.[0] || '';
  if (hasClass(open, 'cover')) return 'cover';
  if (hasClass(open, 'section-divider')) return 'divider';
  if (/\bagenda-row\b/i.test(section)) return 'agenda';
  if (/\bclass=["'][^"']*\bstep\b/i.test(section)) return 'steps';
  if (/\bclass=["'][^"']*\bcard\b/i.test(section)) return 'cards';
  return 'content';
}

function planSlide(section: string): SlidesPptxPlanSlide {
  const kind = classify(section);
  const texts: string[] = [];
  const eyebrow =
    kind === 'divider'
      ? inner(section, 'div', 'divider-eyebrow')
      : inner(section, 'div', 'eyebrow');
  const title =
    kind === 'divider'
      ? inner(section, 'div', 'divider-title')
      : inner(section, 'h1');
  const subtitle =
    kind === 'divider'
      ? inner(section, 'div', 'divider-sub')
      : inner(section, 'p', 'subtitle');
  const hook = inner(section, 'div', 'hook');
  const footer = inner(section, 'div', 'footer');
  if (eyebrow) texts.push(eyebrow);
  if (title) texts.push(title);
  if (subtitle) texts.push(subtitle);
  if (hook) texts.push(hook);
  for (const h2 of allInner(section, 'h2')) texts.push(h2);
  for (const li of allInner(section, 'li')) texts.push(li);
  for (const p of allInner(section, 'p')) {
    if (p !== subtitle) texts.push(p);
  }
  return {
    kind,
    ...(eyebrow ? { eyebrow } : {}),
    ...(title ? { title } : {}),
    ...(subtitle ? { subtitle } : {}),
    ...(hook ? { hook } : {}),
    ...(footer ? { footer } : {}),
    texts,
  };
}

/** Derive the PPTX reconstruction plan from deck HTML (no pptxgenjs). */
export function planSlidesPptxFromHtml(html: string): SlidesPptxPlan {
  const vars = cssVars(html);
  const sections = html.match(SECTION_RE) ?? [];
  const slides = sections.map(planSlide);
  const cover = slides.find((s) => s.kind === 'cover') ?? slides[0];
  return {
    stage: {
      widthPx: SLIDES_PPTX_STAGE_WIDTH_PX,
      heightPx: SLIDES_PPTX_STAGE_HEIGHT_PX,
      widthIn: SLIDES_PPTX_WIDTH_IN,
      heightIn: SLIDES_PPTX_HEIGHT_IN,
      dpi: SLIDES_PPTX_DPI,
    },
    colors: {
      panel: normalizeHex(vars.panel, 'ffffff'),
      ink: normalizeHex(vars.ink, '1a1a1a'),
      muted: normalizeHex(vars.muted, '6b6b6b'),
      accent: normalizeHex(vars.accent, '1a1a1a'),
      card: normalizeHex(vars.card, 'fafaf8'),
    },
    coverH1: cover?.title ?? null,
    coverSubtitle: cover?.subtitle ?? null,
    slideCount: slides.length,
    slides,
  };
}

/**
 * Classic-script walker installed as window.buildPptx. Reads live .slide
 * nodes so agent HTML edits export without touching script strings.
 */
export const SLIDES_PPTX_FROM_DOM_FN = `/* ${SLIDES_PPTX_FROM_DOM_FINGERPRINT} */
async function buildPptx() {
  if (typeof PptxGenJS === "undefined") throw new Error("PptxGenJS failed to load");
  var slides = document.querySelectorAll("main.deck > section.slide, .deck > section.slide");
  if (!slides.length) throw new Error("No .slide sections to export");
  var pptx = new PptxGenJS();
  pptx.defineLayout({ name: "LAYOUT_16x9", width: 13.333, height: 7.5 });
  pptx.layout = "LAYOUT_16x9";
  var I = function (px) { return px / 96; };
  var hex = function (raw, fallback) {
    var s = String(raw || fallback || "").trim();
    var m = s.match(/#([0-9a-fA-F]{6})/);
    if (m) return m[1];
    m = s.match(/#([0-9a-fA-F]{3})\\b/);
    if (m) {
      var a = m[1];
      return a.charAt(0) + a.charAt(0) + a.charAt(1) + a.charAt(1) + a.charAt(2) + a.charAt(2);
    }
    m = s.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
    if (m) {
      return [m[1], m[2], m[3]].map(function (n) {
        return ("0" + Number(n).toString(16)).slice(-2);
      }).join("");
    }
    return String(fallback || "ffffff").replace("#", "");
  };
  var cssUrl = function (name) {
    try {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      var m = v.match(/url\\(["']?(data:[^"')]+)["']?\\)/);
      return m ? m[1] : "";
    } catch (e) {
      return "";
    }
  };
  var root;
  try { root = getComputedStyle(document.documentElement); } catch (e) { root = null; }
  var prop = function (name, fb) {
    return hex(root ? root.getPropertyValue(name) : "", fb);
  };
  var C = {
    bg: prop("--panel", "ffffff"),
    ink: prop("--ink", "1a1a1a"),
    muted: prop("--muted", "6b6b6b"),
    accent: prop("--accent", "1a1a1a"),
    card: prop("--card", "fafaf8")
  };
  var txt = function (s, t, x, y, w, h, o) {
    if (!t) return;
    s.addText(t, Object.assign({
      x: I(x), y: I(y), w: I(w), h: I(h), fontFace: "Arial", margin: 0
    }, o || {}));
  };
  var textOf = function (el) {
    return el ? String(el.textContent || "").replace(/\\s+/g, " ").trim() : "";
  };
  var first = function (rootEl, sel) {
    try { return rootEl.querySelector(sel); } catch (e) { return null; }
  };
  var heroData = cssUrl("--hero");
  var divData = cssUrl("--div1");
  try {
    if (!heroData && typeof IMG !== "undefined" && IMG && IMG.hero) heroData = IMG.hero;
    if (!divData && typeof IMG !== "undefined" && IMG && IMG.d1) divData = IMG.d1;
  } catch (e) {}
  var coverH1 = "";
  for (var i = 0; i < slides.length; i++) {
    var el = slides[i];
    var s = pptx.addSlide();
    s.background = { color: C.bg };
    var footerEl = first(el, ".footer");
    var footerLeft = "";
    var footerRight = "";
    if (footerEl) {
      var spans = footerEl.querySelectorAll(":scope > span");
      footerLeft = textOf(spans[0]) || textOf(footerEl);
      footerRight = spans.length > 1 ? textOf(spans[spans.length - 1]) : "";
    }
    var drawFooter = function () {
      if (footerLeft) txt(s, footerLeft, 56, 686, 900, 20, { fontSize: 9, color: C.muted });
      if (footerRight) txt(s, footerRight, 1100, 686, 124, 20, { fontSize: 9, color: C.muted, align: "right" });
    };
    if (el.classList.contains("cover")) {
      if (heroData) {
        try { s.addImage({ data: heroData, x: 0, y: 0, w: I(1280), h: I(300) }); } catch (e) {}
      } else {
        s.addShape(pptx.ShapeType.rect, {
          x: 0, y: 0, w: I(1280), h: I(300),
          fill: { color: prop("--hero-fallback", "eae8e1") }
        });
      }
      var cEyebrow = textOf(first(el, ".eyebrow"));
      var cH1 = textOf(first(el, "h1"));
      var cSub = textOf(first(el, ".subtitle"));
      var cHook = textOf(first(el, ".hook"));
      if (!coverH1) coverH1 = cH1;
      if (cEyebrow) txt(s, cEyebrow.toUpperCase(), 56, 340, 1168, 24, { fontSize: 12, color: C.accent, bold: true });
      if (cH1) txt(s, cH1, 56, 372, 1168, 64, { fontSize: 32, bold: true, color: C.ink });
      if (cSub) txt(s, cSub, 56, 444, 1168, 44, { fontSize: 14, color: C.muted });
      if (cHook) txt(s, cHook, 56, 496, 1168, 28, { fontSize: 13, bold: true, color: C.accent });
      continue;
    }
    if (el.classList.contains("section-divider")) {
      if (divData) {
        try { s.addImage({ data: divData, x: 0, y: 0, w: I(1280), h: I(720) }); } catch (e) {}
      }
      var dEyebrow = textOf(first(el, ".divider-eyebrow"));
      var dNum = textOf(first(el, ".divider-number"));
      var dTitle = textOf(first(el, ".divider-title"));
      var dSub = textOf(first(el, ".divider-sub"));
      if (dEyebrow) txt(s, dEyebrow.toUpperCase(), 56, 180, 1168, 24, { fontSize: 12, bold: true, color: C.accent });
      if (dNum) txt(s, dNum, 56, 210, 1168, 110, { fontSize: 72, bold: true, color: C.ink });
      if (dTitle) txt(s, dTitle, 56, 330, 1168, 56, { fontSize: 32, bold: true, color: C.ink });
      if (dSub) txt(s, dSub, 56, 396, 900, 40, { fontSize: 14, color: C.muted });
      continue;
    }
    var eyebrow = textOf(first(el, ":scope > .eyebrow")) || textOf(first(el, ".eyebrow"));
    var h1 = textOf(first(el, ":scope > h1")) || textOf(first(el, "h1"));
    if (eyebrow) txt(s, eyebrow.toUpperCase(), 56, 48, 1168, 20, { fontSize: 11, bold: true, color: C.accent });
    if (h1) txt(s, h1, 56, 76, 1168, 44, { fontSize: 26, bold: true, color: C.ink });
    var agendaRows = el.querySelectorAll(".agenda-row");
    if (agendaRows.length) {
      for (var ar = 0; ar < agendaRows.length; ar++) {
        var row = agendaRows[ar];
        var y = 140 + ar * 90;
        s.addShape(pptx.ShapeType.rect, { x: I(56), y: I(y), w: I(1168), h: I(76), fill: { color: C.card } });
        txt(s, textOf(first(row, ".agenda-num")), 76, y + 18, 48, 40, { fontSize: 20, bold: true, color: C.accent });
        txt(s, textOf(first(row, "h2")), 130, y + 14, 820, 28, { fontSize: 16, bold: true, color: C.ink });
        txt(s, textOf(first(row, "p")), 130, y + 42, 820, 24, { fontSize: 12, color: C.muted });
        var kids = row.children;
        if (kids.length) {
          txt(s, textOf(kids[kids.length - 1]), 980, y + 24, 220, 28, { fontSize: 12, color: C.muted, align: "right" });
        }
      }
      drawFooter();
      continue;
    }
    var stepNodes = el.querySelectorAll(".step");
    if (stepNodes.length) {
      for (var st = 0; st < stepNodes.length; st++) {
        var step = stepNodes[st];
        var col = st % 2;
        var srow = Math.floor(st / 2);
        var sx = 56 + col * 596;
        var sy = 140 + srow * 220;
        s.addShape(pptx.ShapeType.rect, { x: I(sx), y: I(sy), w: I(576), h: I(200), fill: { color: C.card } });
        s.addShape(pptx.ShapeType.rect, { x: I(sx), y: I(sy), w: I(6), h: I(200), fill: { color: C.accent } });
        txt(s, textOf(first(step, ".step-n")), sx + 24, sy + 28, 60, 40, { fontSize: 24, bold: true, color: C.accent });
        txt(s, textOf(first(step, "h2")), sx + 90, sy + 36, 450, 32, { fontSize: 16, bold: true, color: C.ink });
        txt(s, textOf(first(step, "p")), sx + 24, sy + 84, 528, 90, { fontSize: 13, color: C.muted });
      }
      drawFooter();
      continue;
    }
    var cards = el.querySelectorAll(".card");
    if (cards.length) {
      var n = cards.length;
      var cols = n >= 4 ? 4 : (n === 3 ? 3 : 2);
      var gap = 18;
      var avail = 1168;
      var cw = (avail - gap * (cols - 1)) / cols;
      var ch = 360;
      for (var ci = 0; ci < n; ci++) {
        var card = cards[ci];
        var ccol = ci % cols;
        var crow = Math.floor(ci / cols);
        var cx = 56 + ccol * (cw + gap);
        var cy = 140 + crow * (ch + gap);
        s.addShape(pptx.ShapeType.rect, { x: I(cx), y: I(cy), w: I(cw), h: I(ch), fill: { color: C.card } });
        var pill = textOf(first(card, ".pill"));
        var ch2 = textOf(first(card, "h2"));
        var cp = textOf(first(card, "p"));
        var lis = [];
        var liNodes = card.querySelectorAll("li");
        for (var li = 0; li < liNodes.length; li++) {
          var lt = textOf(liNodes[li]);
          if (lt) lis.push(lt);
        }
        var ty = cy + 22;
        if (pill) { txt(s, pill.toUpperCase(), cx + 20, ty, cw - 40, 20, { fontSize: 10, bold: true, color: C.accent }); ty += 26; }
        if (ch2) { txt(s, ch2, cx + 20, ty, cw - 40, 28, { fontSize: 16, bold: true, color: C.ink }); ty += 36; }
        if (lis.length) {
          txt(s, lis.map(function (item) { return "• " + item; }).join("\\n"), cx + 20, ty, cw - 40, Math.max(40, ch - (ty - cy) - 20), { fontSize: 13, color: C.muted, valign: "top" });
        } else if (cp) {
          txt(s, cp, cx + 20, ty, cw - 40, Math.max(40, ch - (ty - cy) - 20), { fontSize: 13, color: C.muted, valign: "top" });
        }
      }
      drawFooter();
      continue;
    }
    var gSub = textOf(first(el, ".subtitle"));
    var gy = 136;
    if (gSub) { txt(s, gSub, 56, gy, 1168, 36, { fontSize: 14, color: C.muted }); gy += 44; }
    var paras = el.querySelectorAll(":scope > p");
    for (var pi = 0; pi < paras.length; pi++) {
      var pt = textOf(paras[pi]);
      if (!pt || pt === gSub) continue;
      txt(s, pt, 56, gy, 1168, 48, { fontSize: 14, color: C.muted });
      gy += 52;
    }
    drawFooter();
  }
  var title = coverH1 || textOf(document.querySelector("main.deck h1, .deck h1")) || "Presentation";
  pptx.title = title;
  var safe = title.replace(/[^\\w]+/g, "_").replace(/^_|_$/g, "") || "Presentation";
  return pptx.writeFile({ fileName: safe + ".pptx" });
}`;

export const SLIDES_PPTX_FROM_DOM_SCRIPT = `<script id="${SLIDES_PPTX_FROM_DOM_SCRIPT_ID}">
(function () {
  ${SLIDES_PPTX_FROM_DOM_FN}
  window.buildPptx = buildPptx;
})();
</script>`;
