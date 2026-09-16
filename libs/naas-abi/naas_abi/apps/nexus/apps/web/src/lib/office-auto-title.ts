/** Chat-style title from the first user prompt, plus office topic derivation. */

export const CHAT_TITLE_MAX_CHARS = 50;
const MAX_TITLE_WORDS = 8;
const MAX_TITLE_CHARS = 64;

export function conversationTitleFromPrompt(message: string): string {
  const text = (message || '').trim();
  if (!text) return '';
  return text.length <= CHAT_TITLE_MAX_CHARS
    ? text
    : `${text.slice(0, CHAT_TITLE_MAX_CHARS)}...`;
}

export function firstUserPrompt(
  current: string,
  messages?: Array<{ role?: string; content?: string }> | null,
): string {
  for (const message of messages || []) {
    const text = (message.content || '').trim();
    if (message.role === 'user' && text) return text;
  }
  return (current || '').trim();
}

const PLACEHOLDER_DOCUMENT = new Set([
  'document',
  'my document',
  'new document',
  'nouveau document',
  'nouvelle document',
  'document title',
  'presentation title',
  'sans titre',
  'sections',
  'titre de la document',
  'untitled',
  'untitled document',
  'untitled sections',
]);

const PLACEHOLDER_DECK = new Set([
  'deck',
  'my presentation',
  'new deck',
  'new presentation',
  'nouveau deck',
  'nouvelle presentation',
  'presentation',
  'presentation title',
  'sans titre',
  'slides',
  'titre de la presentation',
  'untitled',
  'untitled deck',
  'untitled presentation',
  'untitled slides',
]);

const UNTITLED_RE = /^untitled[\s_-]*[a-z0-9]*$/i;
const TRAILING_STOPWORDS = new Set([
  'a',
  'an',
  'and',
  'at',
  'au',
  'aux',
  'avec',
  'by',
  'dans',
  'de',
  'des',
  'du',
  'en',
  'et',
  'for',
  'from',
  'in',
  'la',
  'le',
  'les',
  'of',
  'on',
  'or',
  'ou',
  'par',
  'pour',
  'sur',
  'the',
  'to',
  'un',
  'une',
  'with',
]);

function normalize(text: string): string {
  return (text || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
}

function fold(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/\p{M}/gu, '');
}

function isPlaceholder(title: string, placeholders: Set<string>): boolean {
  const text = normalize(title);
  if (!text) return true;
  const folded = fold(text).replace(/^[ .:-]+/, '').replace(/[ .:-]+$/, '');
  if (placeholders.has(folded)) return true;
  return UNTITLED_RE.test(folded);
}

export function isPlaceholderDocumentTitle(title: string): boolean {
  return isPlaceholder(title, PLACEHOLDER_DOCUMENT);
}

export function isPlaceholderDeckTitle(title: string): boolean {
  return isPlaceholder(title, PLACEHOLDER_DECK);
}

const DOCUMENT_NOUN_RE =
  /\b(?:pr[ée]sentations?|documents?|section\s*documents?|sections?|m[ée]mos?|memorandums?|reports?|rapports?|articles?|briefings?|notes?|papers?|essays?|pitchs?|expos[ée]s?)\b/gi;
const DECK_NOUN_RE =
  /\b(?:pr[ée]sentations?|diaporamas?|slide\s*decks?|slideshows?|slides?|decks?|pitchs?|expos[ée]s?)\b/gi;
const CONNECTOR_RE =
  /^[\s,:;-]*(?:au\s+sujet\s+d[eu']|[àa]\s+propos\s+d[eu']|concernant|regarding|covering|about|around|sur|on|pour|for|de\s+la|de\s+l['’]|des|du|d['’]|de)(?=[\s'’])[\s'’]*/i;
const LEADING_ARTICLE_RE =
  /^(?:l['’]|d['’]|(?:les|le|la|des|du|de|un|une|the|a|an|some|my|our)\s+)/i;
const HAS_LETTER_RE = /[^\W\d_]/u;

function cutAtSentenceEnd(text: string): string {
  return text.split(/[.!?;\n]/, 1)[0] || '';
}

function trimEdges(text: string): string {
  return text.replace(/^[\s\t,:;·"'“”«»()[\]]+|[\s\t,:;·"'“”«»()[\]]+$/g, '');
}

function limit(text: string): string {
  let words = text.split(/\s+/).filter(Boolean).slice(0, MAX_TITLE_WORDS);
  while (words.length && words.join(' ').length > MAX_TITLE_CHARS) {
    words.pop();
  }
  while (
    words.length &&
    TRAILING_STOPWORDS.has(fold(trimEdges(words[words.length - 1] || '')))
  ) {
    words.pop();
  }
  return words.join(' ');
}

function capitalizeFirst(text: string): string {
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (ch && /\p{L}/u.test(ch)) {
      if (ch === ch.toLowerCase() && ch !== ch.toUpperCase()) {
        return text.slice(0, i) + ch.toUpperCase() + text.slice(i + 1);
      }
      return text;
    }
  }
  return text;
}

function tidyTopic(topic: string): string {
  let text = trimEdges(cutAtSentenceEnd(normalize(topic)));
  text = text.replace(LEADING_ARTICLE_RE, '');
  text = limit(trimEdges(text));
  if (!HAS_LETTER_RE.test(text)) return '';
  return capitalizeFirst(text);
}

function deriveTopic(brief: string, nounRe: RegExp): string {
  const text = normalize(brief);
  if (!text) return '';
  nounRe.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = nounRe.exec(text))) {
    const rest = text.slice(match.index + match[0].length);
    const connector = CONNECTOR_RE.exec(rest);
    if (!connector) continue;
    const topic = tidyTopic(rest.slice(connector[0].length));
    if (topic) return topic;
  }
  return '';
}

export function deriveDocumentTitle(brief: string): string {
  const text = normalize(brief);
  if (!text || isPlaceholderDocumentTitle(text)) return '';
  return deriveTopic(text, DOCUMENT_NOUN_RE);
}

export function deriveDeckTitle(brief: string): string {
  const text = normalize(brief);
  if (!text || isPlaceholderDeckTitle(text)) return '';
  return deriveTopic(text, DECK_NOUN_RE);
}

export function autoDocumentTitle(brief: string): string {
  return deriveDocumentTitle(brief) || conversationTitleFromPrompt(brief);
}

export function autoDeckTitle(brief: string): string {
  return deriveDeckTitle(brief) || conversationTitleFromPrompt(brief);
}

export function shouldAutoTitleDocument(title: string | null | undefined, slug?: string | null): boolean {
  return isPlaceholderDocumentTitle((title || '').trim() || slug || '');
}

export function shouldAutoTitleDeck(title: string | null | undefined, slug?: string | null): boolean {
  return isPlaceholderDeckTitle((title || '').trim() || slug || '');
}
