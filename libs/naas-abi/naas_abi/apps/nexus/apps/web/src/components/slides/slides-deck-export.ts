/**
 * Client-side deck exports from live HTML (same `.slide` DOM model as PPTX).
 * Google Slides parity: File → Download → format.
 */

import { downloadTextFile } from '@/lib/chat-transcript-export';
import {
  planSlidesPptxFromHtml,
  type SlidesPptxPlanSlide,
} from './slides-pptx-from-dom';

export type SlidesDeckDownloadFormat =
  | 'pptx'
  | 'pdf'
  | 'markdown'
  | 'plain-text'
  | 'html';

const PRINT_CSS = `
@page { size: 13.333in 7.5in; margin: 0; }
@media print {
  body { margin: 0; background: white; }
  .deck-menubar { display: none !important; }
  main.deck, .deck { padding-top: 0 !important; gap: 0 !important; }
  section.slide {
    page-break-after: always;
    break-after: page;
    border: none !important;
  }
}
`;

export function sanitizeDeckFilename(title: string): string {
  const slug =
    title
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 64) || 'presentation';
  return slug;
}

export function deckExportFilename(title: string, ext: string): string {
  const stem = sanitizeDeckFilename(title);
  if (ext === 'html') {
    return `${stem}.slides.html`;
  }
  return `${stem}.${ext}`;
}

function slideHeading(index: number, slide: SlidesPptxPlanSlide): string {
  const label = slide.title || slide.eyebrow || `Slide ${index + 1}`;
  const kind =
    slide.kind === 'cover'
      ? 'Cover'
      : slide.kind === 'divider'
        ? 'Section'
        : slide.kind === 'agenda'
          ? 'Agenda'
          : slide.kind === 'cards'
            ? 'Cards'
            : slide.kind === 'steps'
              ? 'Steps'
              : 'Content';
  return `Slide ${index + 1} — ${kind}: ${label}`;
}

/** Markdown export: one H2 per slide, structured body copy. */
export function deckHtmlToMarkdown(html: string, title: string): string {
  const plan = planSlidesPptxFromHtml(html);
  const deckTitle = title.trim() || plan.coverH1 || 'Presentation';
  const lines: string[] = [
    `# ${deckTitle}`,
    '',
    `_Exported ${new Date().toISOString()}_`,
    `_Slides: ${plan.slideCount}_`,
    '',
  ];

  plan.slides.forEach((slide, index) => {
    lines.push('---', '', `## ${slideHeading(index, slide)}`, '');
    if (slide.eyebrow && slide.eyebrow !== slide.title) {
      lines.push(`_${slide.eyebrow}_`, '');
    }
    if (slide.title) {
      lines.push(`### ${slide.title}`, '');
    }
    if (slide.subtitle) {
      lines.push(slide.subtitle, '');
    }
    if (slide.hook) {
      lines.push(`> ${slide.hook}`, '');
    }
    const body = slide.texts.filter(
      (t) =>
        t !== slide.eyebrow &&
        t !== slide.title &&
        t !== slide.subtitle &&
        t !== slide.hook &&
        !(slide.footer && t === slide.footer),
    );
    for (const line of body) {
      if (/^[-•]/.test(line)) {
        lines.push(line.startsWith('-') ? line : `- ${line}`);
      } else if (line.length < 80 && !line.includes('.')) {
        lines.push(`**${line}**`);
      } else {
        lines.push(line);
      }
    }
    if (slide.footer) {
      lines.push('', `_${slide.footer}_`);
    }
    lines.push('');
  });

  return lines.join('\n').trimEnd() + '\n';
}

/** Plain text: slide blocks separated by blank lines. */
export function deckHtmlToPlainText(html: string, title: string): string {
  const plan = planSlidesPptxFromHtml(html);
  const deckTitle = title.trim() || plan.coverH1 || 'Presentation';
  const lines: string[] = [
    deckTitle,
    '='.repeat(Math.min(deckTitle.length, 60)),
    '',
    `Exported: ${new Date().toISOString()}`,
    `Slides: ${plan.slideCount}`,
    '',
  ];

  plan.slides.forEach((slide, index) => {
    lines.push(`--- ${slideHeading(index, slide)} ---`, '');
    for (const text of slide.texts) {
      lines.push(text);
    }
    lines.push('');
  });

  return lines.join('\n').trimEnd() + '\n';
}

export function downloadDeckMarkdown(html: string, title: string): void {
  const content = deckHtmlToMarkdown(html, title);
  downloadTextFile(
    deckExportFilename(title, 'md'),
    content,
    'text/markdown;charset=utf-8',
  );
}

export function downloadDeckPlainText(html: string, title: string): void {
  const content = deckHtmlToPlainText(html, title);
  downloadTextFile(
    deckExportFilename(title, 'txt'),
    content,
    'text/plain;charset=utf-8',
  );
}

export function downloadDeckHtml(html: string, title: string): void {
  downloadTextFile(
    deckExportFilename(title, 'html'),
    html,
    'text/html;charset=utf-8',
  );
}

export function injectPrintStyles(html: string): string {
  const tag = '<style id="nexus-slides-print">';
  if (html.includes('</head>')) {
    return html.replace('</head>', `${tag}${PRINT_CSS}</style></head>`);
  }
  return `<!doctype html><html><head>${tag}${PRINT_CSS}</style></head><body>${html}</body></html>`;
}

/**
 * Opens the system print dialog (Save as PDF in Chrome/Safari).
 * Pixel-accurate to the HTML deck; no server render.
 */
export function printDeckPdf(html: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof document === 'undefined') {
      reject(new Error('PDF export is only available in the browser.'));
      return;
    }

    const iframe = document.createElement('iframe');
    iframe.setAttribute('title', 'Slides PDF export');
    iframe.style.cssText =
      'position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0;pointer-events:none;';
    document.body.appendChild(iframe);

    const win = iframe.contentWindow;
    const doc = iframe.contentDocument;
    if (!win || !doc) {
      document.body.removeChild(iframe);
      reject(new Error('Print frame unavailable.'));
      return;
    }

    let settled = false;
    const cleanup = () => {
      if (settled) return;
      settled = true;
      iframe.remove();
      resolve();
    };

    win.onafterprint = cleanup;
    window.setTimeout(cleanup, 120_000);

    doc.open();
    doc.write(injectPrintStyles(html));
    doc.close();

    window.setTimeout(() => {
      try {
        win.focus();
        win.print();
      } catch (err) {
        iframe.remove();
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    }, 400);
  });
}
