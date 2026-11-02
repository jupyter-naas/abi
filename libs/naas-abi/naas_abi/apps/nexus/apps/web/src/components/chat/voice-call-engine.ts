/**
 * Voice call engine: sentence aggregator, backchannel classifier and turn detection.
 *
 * Implements the 2026 SOTA cascaded full-duplex voice agent architecture:
 * 1. SentenceAggregator: bridges streaming LLM tokens into speakable sentences
 *    with abbreviation/decimal guards and minimum clause length so TTS starts
 *    on the first complete sentence (<900ms TTFA) while the LLM keeps streaming.
 * 2. Adaptive Interruption vs. Backchannel Gate: distinguishes short listener
 *    acknowledgments ("uh-huh", "okay", "yeah") from true floor-taking barge-ins.
 * 3. Acoustic VAD state machine constants and helpers.
 */

const ABBREVIATIONS = new Set([
  'mr',
  'mrs',
  'ms',
  'dr',
  'prof',
  'sr',
  'jr',
  'st',
  'vs',
  'etc',
  'inc',
  'ltd',
  'co',
  'corp',
  'jan',
  'feb',
  'mar',
  'apr',
  'jun',
  'jul',
  'aug',
  'sep',
  'sept',
  'oct',
  'nov',
  'dec',
  'fig',
  'eq',
  'no',
  'vol',
  'pp',
  'est',
  'approx',
  'dept',
  'univ',
  'assn',
  'bros',
  'gen',
  'col',
  'maj',
  'capt',
  'lt',
  'sgt',
  'cpl',
  'pvt',
  'ave',
  'blvd',
  'rd',
  'mt',
  'ft',
  'e.g',
  'i.e',
  'u.s',
  'u.k',
  'e.u',
  'm',
  'mme',
  'mlle',
]);

/** Minimum characters before flushing a sentence to TTS (avoids 1-word clips). */
export const MIN_SENTENCE_CHARS = 18;

/** First-chunk clause threshold for ultra-low TTFA on comma/colon/dash boundaries. */
export const FIRST_CLAUSE_MIN_CHARS = 42;

/**
 * Strips markdown, URLs, and code fences from a spoken sentence before TTS.
 */
export function cleanSentenceForSpeech(raw: string): string {
  let text = raw.trim();
  if (!text) return '';

  // Remove complete or unclosed code blocks
  text = text.replace(/```[\s\S]*?```/g, ' ');
  text = text.replace(/```[\s\S]*$/g, ' ');
  // Inline code
  text = text.replace(/`([^`]+)`/g, '$1');
  // Markdown images and links
  text = text.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1');
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  // Bare URLs
  text = text.replace(/https?:\/\/\S+/g, ' ');
  // Headings and formatting markers
  text = text.replace(/^#{1,6}\s*/gm, '');
  text = text.replace(/[*_~|>]+/g, ' ');
  text = text.replace(/^\s*[-•]\s+/gm, '');
  text = text.replace(/\s+/g, ' ').trim();

  return text;
}

/**
 * Checks if a period at index `dotIndex` in `buffer` is an abbreviation or decimal.
 */
function isNonTerminalPeriod(buffer: string, dotIndex: number): boolean {
  const before = buffer.slice(0, dotIndex);
  const after = buffer.slice(dotIndex + 1);

  // Decimal number: e.g. "3.14"
  if (/\d$/.test(before) && /^\d/.test(after)) {
    return true;
  }

  // Ellipsis: "..."
  if (before.endsWith('.') || after.startsWith('.')) {
    return true;
  }

  // Extract the word immediately preceding the period
  const wordMatch = before.match(/([a-zA-Z.]+)$/);
  if (!wordMatch) return false;

  const word = wordMatch[1].toLowerCase();
  if (ABBREVIATIONS.has(word)) {
    return true;
  }

  // Single uppercase initial like "J. R. R. Tolkien"
  if (word.length === 1 && /[A-Z]/.test(wordMatch[1])) {
    return true;
  }

  return false;
}

/**
 * Streaming Sentence Aggregator (Pipecat / LiveKit SOTA pattern).
 * Accumulates streaming LLM tokens and yields complete speakable sentences
 * as soon as sentence-ending punctuation (`.`, `!`, `?`, `\n`) is followed by
 * whitespace, while guarding against abbreviations and decimals.
 */
export class SentenceAggregator {
  private buffer = '';
  private emittedCount = 0;

  /**
   * Push a new token chunk and return any complete sentences ready for TTS.
   */
  push(chunk: string): string[] {
    if (!chunk) return [];
    this.buffer += chunk;
    const ready: string[] = [];

    while (true) {
      const splitIdx = this.findSplitIndex();
      if (splitIdx === -1) break;

      const candidateRaw = this.buffer.slice(0, splitIdx).trim();
      this.buffer = this.buffer.slice(splitIdx).trimStart();

      const cleaned = cleanSentenceForSpeech(candidateRaw);
      if (cleaned.length > 0) {
        ready.push(cleaned);
        this.emittedCount += 1;
      }
    }

    return ready;
  }

  /**
   * Flush any remaining text when the LLM stream finishes.
   */
  flush(): string[] {
    const remaining = cleanSentenceForSpeech(this.buffer);
    this.buffer = '';
    if (!remaining) return [];
    this.emittedCount += 1;
    return [remaining];
  }

  /**
   * Reset the aggregator (e.g. on barge-in interruption).
   */
  reset(): void {
    this.buffer = '';
    this.emittedCount = 0;
  }

  private findSplitIndex(): number {
    const buf = this.buffer;
    const minLen = this.emittedCount === 0 ? MIN_SENTENCE_CHARS : 24;

    for (let i = 0; i < buf.length; i++) {
      const ch = buf[i];

      // Hard newline boundary
      if (ch === '\n') {
        const candidate = cleanSentenceForSpeech(buf.slice(0, i));
        if (candidate.length >= minLen) {
          return i + 1;
        }
        continue;
      }

      // Sentence-ending punctuation followed by whitespace or quote+whitespace
      if (ch === '.' || ch === '!' || ch === '?') {
        const nextChar = buf[i + 1];
        if (!nextChar) {
          // Wait for the next token to confirm whether it's followed by space or digit
          continue;
        }
        const isBoundaryAfter =
          /\s/.test(nextChar) ||
          ((nextChar === '"' || nextChar === "'" || nextChar === ')' || nextChar === '”') &&
            Boolean(buf[i + 2] && /\s/.test(buf[i + 2])));

        if (!isBoundaryAfter) continue;
        if (ch === '.' && isNonTerminalPeriod(buf, i)) continue;

        const splitEnd =
          nextChar === '"' || nextChar === "'" || nextChar === ')' || nextChar === '”'
            ? i + 2
            : i + 1;
        const candidate = cleanSentenceForSpeech(buf.slice(0, splitEnd));
        if (candidate.length >= minLen) {
          return splitEnd;
        }
      }

      // First-sentence fast path: if the opening sentence is long and hits a
      // semicolon, colon, or em-dash followed by space, emit the first clause
      // early to cut Time-To-First-Audio (TTFA).
      if (
        this.emittedCount === 0 &&
        i >= FIRST_CLAUSE_MIN_CHARS &&
        (ch === ';' || ch === ':' || ch === '—')
      ) {
        const nextChar = buf[i + 1];
        if (nextChar && /\s/.test(nextChar)) {
          const candidate = cleanSentenceForSpeech(buf.slice(0, i + 1));
          if (candidate.length >= FIRST_CLAUSE_MIN_CHARS) {
            return i + 1;
          }
        }
      }
    }

    return -1;
  }
}

/**
 * Known backchannel / listener acknowledgment phrases (EN + FR) and Whisper
 * silence hallucinations that should NOT interrupt an ongoing agent turn or
 * trigger an empty turn when the user is just nodding along.
 */
const BACKCHANNEL_SET = new Set([
  'uh-huh',
  'uh huh',
  'uhhuh',
  'mm-hmm',
  'mm hmm',
  'mmhmm',
  'mhm',
  'hmm',
  'hm',
  'ah',
  'oh',
  'ok',
  'okay',
  'right',
  'yeah',
  'yep',
  'yup',
  'sure',
  'got it',
  'i see',
  'oui',
  'ouais',
  'd accord',
  "d'accord",
  'ok merci',
  'entendu',
  'je vois',
  'exact',
]);

/**
 * Whole transcripts Whisper-family models emit on silence or room noise (they
 * learned them from subtitle credits), compared after `normalizeForHallucination`.
 */
const HALLUCINATION_SET = new Set([
  'you',
  'thank you',
  'thanks',
  'thank you very much',
  'thank you so much',
  'thank you for watching',
  'thanks for watching',
  'thank you for watching and see you next time',
  'please subscribe',
  'like and subscribe',
  'bye',
  'bye bye',
  'subtitles by',
  'music',
  'applause',
  'silence',
  'blank audio',
  'merci',
  'merci beaucoup',
  'merci d avoir regardé',
  'sous titres',
  'sous titrage',
  'musique',
  'gracias',
  'muchas gracias',
  'untertitel',
  'vielen dank',
  'danke',
  'grazie',
  'obrigado',
  'спасибо',
  '谢谢',
  '謝謝',
  '谢谢观看',
  '謝謝觀看',
  'ご視聴ありがとうございました',
  'ありがとうございました',
  'ありがとうございます',
  '감사합니다',
]);

/** Subtitle-credit fragments that mark a hallucination anywhere in a short transcript. */
const HALLUCINATION_FRAGMENT_RE =
  /amara ?org|subtitles? by|sous titr|untertitel|字幕|ご視聴|不吝|点赞|點贊|订阅|訂閱|thanks? (?:you )?for watching/;

export function normalizeUtterance(text: string): string {
  return text
    .toLowerCase()
    .replace(/[.,!?;:"“”()[\]]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Lowercases and drops every Unicode punctuation or symbol (`。`, `¡`, `♪`, `-`). */
export function normalizeForHallucination(text: string): string {
  return text
    .toLowerCase()
    .replace(/[\p{P}\p{S}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Returns true if the transcript is a known STT silence hallucination: empty,
 * punctuation or music notes only, a stock subtitle phrase, or a subtitle credit.
 */
export function isSilenceHallucination(text: string): boolean {
  const norm = normalizeForHallucination(text);
  if (!norm) return true;
  if (HALLUCINATION_SET.has(norm)) return true;
  return norm.length <= 80 && HALLUCINATION_FRAGMENT_RE.test(norm);
}

export type Script = 'latin' | 'cjk' | 'cyrillic' | 'arabic' | 'devanagari' | 'other';

const SCRIPT_RES: [Exclude<Script, 'other'>, RegExp][] = [
  ['latin', /\p{Script=Latin}/u],
  ['cjk', /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u],
  ['cyrillic', /\p{Script=Cyrillic}/u],
  ['arabic', /\p{Script=Arabic}/u],
  ['devanagari', /\p{Script=Devanagari}/u],
];

/** The writing system most of the transcript's letters use, or null when it has none. */
export function dominantScript(text: string): Script | null {
  const counts = new Map<Script, number>();
  for (const ch of text) {
    if (!/\p{L}/u.test(ch)) continue;
    const script = SCRIPT_RES.find(([, re]) => re.test(ch))?.[0] ?? 'other';
    counts.set(script, (counts.get(script) ?? 0) + 1);
  }
  let best: Script | null = null;
  let bestCount = 0;
  for (const [script, count] of counts) {
    if (count > bestCount) {
      best = script;
      bestCount = count;
    }
  }
  return best;
}

const LANGUAGE_SCRIPTS: Record<string, Script> = {
  zh: 'cjk',
  ja: 'cjk',
  ko: 'cjk',
  ru: 'cyrillic',
  uk: 'cyrillic',
  bg: 'cyrillic',
  sr: 'cyrillic',
  ar: 'arabic',
  fa: 'arabic',
  ur: 'arabic',
  hi: 'devanagari',
  mr: 'devanagari',
  ne: 'devanagari',
};

export function scriptForLanguage(lang: string | null | undefined): Script {
  return LANGUAGE_SCRIPTS[(lang || '').toLowerCase()] ?? 'latin';
}

/** Longest foreign-script transcript treated as noise rather than a real switch of language. */
export const FOREIGN_SCRIPT_MAX_CHARS = 24;

/**
 * True for a short transcript in a script the call is not using (e.g. "谢谢。"
 * or "все" on a French or English call): Whisper guessing a language from noise.
 */
export function isForeignScriptNoise(text: string, expectedLang: string | null | undefined): boolean {
  const script = dominantScript(text);
  // Latin words ("OK", product names) are common on every call, so never drop them.
  if (!script || script === 'latin') return false;
  if (script === scriptForLanguage(expectedLang)) return false;
  return normalizeForHallucination(text).length <= FOREIGN_SCRIPT_MAX_CHARS;
}

const LANGUAGE_MARKERS: Record<string, Set<string>> = {
  en: new Set(['the', 'and', 'you', 'is', 'are', 'what', 'how', 'can', 'please', 'this', 'that', 'with', 'i']),
  fr: new Set(['le', 'la', 'les', 'et', 'est', 'je', 'tu', 'vous', 'nous', 'que', 'pour', 'avec', 'pas', 'une', 'des', 'bonjour', 'merci', 'oui']),
  es: new Set(['el', 'los', 'las', 'que', 'es', 'por', 'para', 'con', 'una', 'hola', 'gracias', 'pero', 'como']),
  de: new Set(['der', 'die', 'das', 'und', 'ist', 'ich', 'du', 'nicht', 'mit', 'ein', 'eine', 'hallo', 'danke']),
  it: new Set(['il', 'che', 'di', 'per', 'con', 'una', 'sono', 'ciao', 'grazie', 'non', 'questo']),
  pt: new Set(['o', 'os', 'que', 'para', 'com', 'uma', 'não', 'você', 'olá', 'obrigado', 'isso']),
};

/** Guess a Latin-script language from text by stopword hits; null when unsure. */
export function guessLatinLanguage(text: string): string | null {
  const words = normalizeForHallucination(text).split(' ').filter(Boolean);
  let best: string | null = null;
  let bestHits = 0;
  let secondHits = 0;
  for (const [lang, markers] of Object.entries(LANGUAGE_MARKERS)) {
    const hits = words.filter((w) => markers.has(w)).length;
    if (hits > bestHits) {
      secondHits = bestHits;
      bestHits = hits;
      best = lang;
    } else if (hits > secondHits) {
      secondHits = hits;
    }
  }
  return bestHits >= 2 && bestHits > secondHits ? best : null;
}

/**
 * ISO-639-1 hint for `/api/transcribe`: the language of the user's recent turns
 * when they make it clear, else the browser's language.
 */
export function callLanguageHint(
  recentUserTexts: string[],
  browserLanguage: string | null | undefined,
): string | null {
  const recent = guessLatinLanguage(recentUserTexts.slice(-4).join(' '));
  if (recent) return recent;
  const code = (browserLanguage || '').toLowerCase().split(/[-_]/)[0];
  return /^[a-z]{2}$/.test(code) ? code : null;
}

function letterBigrams(text: string): Map<string, number> {
  const letters = text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[^\p{L}\p{N}]+/gu, '');
  const grams = new Map<string, number>();
  for (let i = 0; i < letters.length - 1; i++) {
    const gram = letters.slice(i, i + 2);
    grams.set(gram, (grams.get(gram) ?? 0) + 1);
  }
  return grams;
}

/** Dice similarity of letter bigrams, accent- and punctuation-blind (0..1). */
export function transcriptSimilarity(a: string, b: string): number {
  const ga = letterBigrams(a);
  const gb = letterBigrams(b);
  let total = 0;
  let shared = 0;
  for (const n of ga.values()) total += n;
  for (const n of gb.values()) total += n;
  for (const [gram, n] of ga) shared += Math.min(n, gb.get(gram) ?? 0);
  return total === 0 ? 0 : (2 * shared) / total;
}

export const DUPLICATE_TRANSCRIPT_WINDOW_MS = 1000;
export const DUPLICATE_TRANSCRIPT_SIMILARITY = 0.5;

/**
 * Two transcriptions of one utterance. A second real utterance cannot be
 * spoken, closed by silence and transcribed within the window, so a
 * look-alike that arrives that soon is an echo of the first.
 */
export function isNearDuplicateTranscript(
  previous: { text: string; at: number } | null,
  text: string,
  at: number,
): boolean {
  if (!previous || at - previous.at > DUPLICATE_TRANSCRIPT_WINDOW_MS) return false;
  return transcriptSimilarity(previous.text, text) >= DUPLICATE_TRANSCRIPT_SIMILARITY;
}

export interface SpokenSentence {
  turnId: number;
  text: string;
}

/** What the listener heard of one turn: its finished sentences, then the one cut off. */
export function spokenTextForTurn(
  spoken: SpokenSentence[],
  turnId: number,
  current: SpokenSentence | null,
): string {
  return [...spoken, ...(current ? [current] : [])]
    .filter((s) => s.turnId === turnId)
    .map((s) => s.text)
    .join(' ')
    .trim();
}

/** Bubble text after a barge-in: what was heard, else what had streamed. */
export function interruptedMessageContent(spokenText: string, streamedContent: string): string {
  if (streamedContent.endsWith('[interrupted]')) return streamedContent;
  const body = spokenText || streamedContent.replace(/▌$/, '').trim();
  return body ? `${body} … [interrupted]` : '… [interrupted]';
}

export type CallLanguageSetting = 'auto' | 'en' | 'fr';

export const CALL_LANGUAGES: ReadonlyArray<{ id: CallLanguageSetting; label: string }> = [
  { id: 'auto', label: 'Auto' },
  { id: 'en', label: 'English' },
  { id: 'fr', label: 'Français' },
];

/** Kokoro English voices; `''` lets the API pick one for the detected language. */
export const CALL_VOICES: ReadonlyArray<{ id: string; label: string }> = [
  { id: '', label: 'Auto' },
  { id: 'af_heart', label: 'Heart (US)' },
  { id: 'af_bella', label: 'Bella (US)' },
  { id: 'am_michael', label: 'Michael (US)' },
  { id: 'bf_emma', label: 'Emma (UK)' },
  { id: 'bm_george', label: 'George (UK)' },
];

/** The API moves sentences this long (and non-English ones) to MAI, which has no Kokoro voices. */
export const KOKORO_MAX_CHARS = 220;

export interface CallSettings {
  language: CallLanguageSetting;
  voice: string;
  inputDeviceId: string;
}

export const DEFAULT_CALL_SETTINGS: CallSettings = { language: 'auto', voice: '', inputDeviceId: '' };

export function parseCallSettings(raw: string | null | undefined): CallSettings {
  try {
    const value = JSON.parse(raw || '{}') as Partial<CallSettings>;
    return {
      language: CALL_LANGUAGES.some((l) => l.id === value.language)
        ? (value.language as CallLanguageSetting)
        : 'auto',
      voice: CALL_VOICES.some((v) => v.id === value.voice) ? (value.voice as string) : '',
      inputDeviceId: typeof value.inputDeviceId === 'string' ? value.inputDeviceId : '',
    };
  } catch {
    return { ...DEFAULT_CALL_SETTINGS };
  }
}

/** The chosen language wins over the guess from recent turns. */
export function resolveCallLanguage(
  setting: CallLanguageSetting,
  recentUserTexts: string[],
  browserLanguage: string | null | undefined,
): string | null {
  return setting === 'auto' ? callLanguageHint(recentUserTexts, browserLanguage) : setting;
}

/** Extra `/api/speech` fields for one sentence. A voice only applies where Kokoro speaks it. */
export function callSpeechOptions(
  settings: Pick<CallSettings, 'language' | 'voice'>,
  textLength: number,
): { language?: string; voice?: string } {
  if (settings.language === 'auto') return {};
  const voice =
    settings.language === 'en' && settings.voice && textLength < KOKORO_MAX_CHARS
      ? settings.voice
      : undefined;
  return voice ? { language: settings.language, voice } : { language: settings.language };
}

export interface UtteranceStats {
  /** Time the speech-band RMS sat above the speech threshold. */
  voicedMs: number;
  /** Mean speech-band RMS over those voiced frames. */
  avgVoicedRms: number;
}

/** A clip too short or too faint to be speech: a door, a click, or a passing voice. */
export function isLikelyNoiseUtterance(stats: UtteranceStats): boolean {
  return (
    stats.voicedMs < TEN_VAD_CONFIG.MIN_VOICED_MS ||
    stats.avgVoicedRms < TEN_VAD_CONFIG.MIN_AVG_VOICED_RMS
  );
}

/** While ABI speaks: cut it off only after a sustained, speech-like burst. */
export function shouldCommitBargeIn(stats: UtteranceStats): boolean {
  return stats.voicedMs >= TEN_VAD_CONFIG.BARGE_IN_COMMIT_MS && !isLikelyNoiseUtterance(stats);
}

/**
 * Speech captured while a reply is in flight takes the floor ('interrupt') only
 * when its transcript is real: not a silence hallucination, not foreign-script
 * noise, not a listener backchannel. Anything else is dropped and the reply goes on.
 */
export function judgeInterjection(
  transcript: string,
  expectedLang: string | null | undefined,
): 'drop' | 'interrupt' {
  if (
    isSilenceHallucination(transcript) ||
    isForeignScriptNoise(transcript, expectedLang) ||
    isBackchannelOnly(transcript)
  ) {
    return 'drop';
  }
  return 'interrupt';
}

/**
 * Classifies whether a user utterance spoken WHILE the agent was speaking
 * is a brief backchannel ("uh-huh", "okay", "yeah") rather than a real
 * floor-taking interruption.
 */
export function isBackchannelOnly(text: string): boolean {
  const norm = normalizeUtterance(text);
  if (!norm) return true;
  return BACKCHANNEL_SET.has(norm);
}

/**
 * TEN Turn Detection 3-state output:
 * - 'finished': complete user turn ready to dispatch to the LLM immediately
 * - 'unfinished': user paused mid-clause / mid-thought; hold the floor open
 * - 'wait': explicit stop/hold/pause command; silence the agent without replying
 */
export type TurnState = 'finished' | 'unfinished' | 'wait';

const WAIT_COMMANDS = new Set([
  'stop',
  'stop it',
  'stop speaking',
  'stop talking',
  'please stop',
  'wait',
  'wait a second',
  'wait a minute',
  'wait a moment',
  'hold on',
  'hold on a second',
  'hold on a minute',
  'hang on',
  'give me a second',
  'give me a moment',
  'give me a minute',
  'one second',
  'one moment',
  'just a second',
  'just a moment',
  'pause',
  'shut up',
  'be quiet',
  'quiet',
  'silence',
  'attends',
  'attendez',
  'attends une seconde',
  'attends un instant',
  'un instant',
  'une seconde',
  'une minute',
  'deux secondes',
  'tais-toi',
  'tais toi',
  'taisez-vous',
  'taisez vous',
  'arrete',
  'arrête',
  'arrete de parler',
  'arrête de parler',
  'stop parle plus',
]);

/**
 * Matches compound / embedded floor-stop commands inside longer conversational
 * utterances (e.g. "No, I didn't even talk about TensorFlow... How about you just stop talking?"
 * or "Okay, that's too long, so I'm going to cut you off right now again. Let's just stop here.")
 */
const EMBEDDED_WAIT_RE =
  /(?:\b(?:just\s+)?stop\s+(?:talking|speaking|here|now|there)\b|\blet'?s\s+(?:just\s+)?stop\s+here\b|\bcut\s+you\s+off\b|\bplease\s+be\s+quiet\b|\bon\s+arr[êe]te\s+l[àa](?=\s|$|[.,!?;:])|(?:^|\s)arr[êe]te\s+de\s+parler\b)/i;

export const DEFAULT_DOMAIN_VOCABULARY =
  'ABI, NaasAI, Nexus, Ontology, BFO, SPARQL, Oxigraph, Qdrant, TEN';

/**
 * Builds a domain + active agent vocabulary hint for STT (`/api/transcribe`)
 * so domain terms and agent names are not misrecognized.
 */
export function buildDomainVocabularyPrompt(agentName?: string | null): string {
  const cleanAgent = (agentName || '').trim();
  if (!cleanAgent || DEFAULT_DOMAIN_VOCABULARY.toLowerCase().includes(cleanAgent.toLowerCase())) {
    return DEFAULT_DOMAIN_VOCABULARY;
  }
  return `${cleanAgent}, ${DEFAULT_DOMAIN_VOCABULARY}`;
}

const UNFINISHED_TRAILING_MULTIWORD = [
  'parce que',
  'puisque',
  'tandis que',
  'alors que',
  'bien que',
  'sans que',
  'avant que',
  'apres que',
  'après que',
  'pour que',
  'afin que',
  'even though',
  'as well as',
  'such as',
  'because of',
  'instead of',
  'in order to',
  'going to',
  'want to',
  'need to',
  'have to',
  'trying to',
  'thinking about',
  'looking at',
  'talking about',
];

const UNFINISHED_TRAILING_WORDS = new Set([
  // English conjunctions, prepositions, determiners, fillers
  'and',
  'or',
  'but',
  'nor',
  'yet',
  'so',
  'because',
  'since',
  'although',
  'though',
  'while',
  'whereas',
  'if',
  'unless',
  'until',
  'when',
  'whenever',
  'where',
  'wherever',
  'whether',
  'that',
  'which',
  'who',
  'whom',
  'whose',
  'like',
  'about',
  'with',
  'without',
  'for',
  'to',
  'from',
  'in',
  'into',
  'on',
  'onto',
  'at',
  'by',
  'of',
  'as',
  'than',
  'between',
  'through',
  'during',
  'before',
  'after',
  'under',
  'over',
  'the',
  'a',
  'an',
  'my',
  'your',
  'our',
  'their',
  'his',
  'her',
  'its',
  'this',
  'these',
  'those',
  'some',
  'any',
  'every',
  'uh',
  'um',
  'er',
  'erm',
  'well',
  // French conjunctions, prepositions, determiners, fillers
  'et',
  'ou',
  'mais',
  'donc',
  'or',
  'ni',
  'car',
  'parce',
  'puisque',
  'comme',
  'quand',
  'lorsque',
  'si',
  'que',
  'qui',
  'dont',
  'où',
  'pour',
  'avec',
  'sans',
  'dans',
  'sur',
  'sous',
  'vers',
  'chez',
  'de',
  'du',
  'des',
  'à',
  'au',
  'aux',
  'par',
  'en',
  'le',
  'la',
  'les',
  'un',
  'une',
  'mon',
  'ton',
  'son',
  'notre',
  'votre',
  'leur',
  'ce',
  'cet',
  'cette',
  'ces',
  'euh',
  'ben',
  'bah',
]);

/**
 * TEN Turn Detection semantic turn classifier (`finished` | `unfinished` | `wait`).
 * Evaluates linguistic completeness and floor-control intent of a transcribed
 * user utterance.
 */
export function classifyTurnState(text: string): TurnState {
  const raw = text.trim();
  const norm = normalizeUtterance(raw);
  if (!norm) return 'wait';

  // 1. Explicit or compound/embedded wait / stop / hold commands
  if (WAIT_COMMANDS.has(norm) || EMBEDDED_WAIT_RE.test(raw)) {
    return 'wait';
  }

  // 2. Explicit trailing ellipsis, comma, colon, or dash indicates mid-thought pause
  if (/(?:\.\.\.|…|[,;:\-—])$/.test(raw)) {
    return 'unfinished';
  }

  // If the user explicitly asked a question or exclaimed, treat as finished unless
  // it's a single filler word.
  const hasStrongTerminal = /[?!]["'”)]*$/.test(raw);
  if (hasStrongTerminal) {
    return 'finished';
  }

  // 3. Check multi-word trailing connectors
  for (const phrase of UNFINISHED_TRAILING_MULTIWORD) {
    if (norm === phrase || norm.endsWith(` ${phrase}`)) {
      return 'unfinished';
    }
  }

  // 4. Check last token for trailing conjunction / preposition / article / filler
  const words = norm.split(' ').filter(Boolean);
  const lastWord = words[words.length - 1] ?? '';
  if (UNFINISHED_TRAILING_WORDS.has(lastWord)) {
    return 'unfinished';
  }

  return 'finished';
}

/**
 * TEN VAD frame-level and full-duplex turn-taking timing constants.
 * Modeled on TEN-VAD (16ms hop size, fast speech onset, rapid hangover,
 * reversible 150ms ducking, and 380ms full barge-in commit).
 */
export const TEN_VAD_CONFIG = {
  /** 16ms frame hop matching TEN-VAD 256-sample frame @ 16kHz */
  HOP_INTERVAL_MS: 16,
  /** Consecutive speech frames (~64ms) required to trigger speech onset */
  ONSET_FRAMES: 4,
  /** RMS threshold when agent is silent (listening mode) */
  SPEECH_RMS_THRESHOLD: 0.022,
  /** Elevated RMS threshold while agent TTS plays to reject speaker bleed */
  BARGE_IN_RMS_THRESHOLD: 0.032,
  /** Sustained user voice duration (ms) during TTS before ducking agent volume */
  DUCKING_HOLD_MS: 150,
  /** Sustained user voice duration (ms) during TTS to commit a full barge-in */
  BARGE_IN_COMMIT_MS: 380,
  /** Post-speech silence hangover (ms) before committing a normal user turn */
  FINISHED_SILENCE_MS: 520,
  /** Extended continuation window (ms) when TEN Turn Detection marks turn 'unfinished' */
  UNFINISHED_WAIT_MS: 1800,
  /** Maximum single utterance recording duration (ms) before forced flush */
  MAX_UTTERANCE_MS: 30000,
  /** Minimum voiced time (ms) in an utterance before it is sent to STT */
  MIN_VOICED_MS: 250,
  /** Minimum mean speech-band RMS over voiced frames before it is sent to STT */
  MIN_AVG_VOICED_RMS: 0.03,
} as const;

/**
 * Computes a speech-weighted RMS level in [0, 1] from WebAudio AnalyserNode buffers.
 * Combines time-domain RMS with speech-band (300-3400 Hz) frequency energy when
 * available so low-frequency desk thumps or high-frequency clicks do not false-trigger.
 */
export function computeSpeechBandRms(
  timeDomainData: Uint8Array,
  freqData?: Uint8Array,
  sampleRate = 48000,
): number {
  if (timeDomainData.length === 0) return 0;

  let sumSq = 0;
  for (let i = 0; i < timeDomainData.length; i++) {
    const sample = (timeDomainData[i] - 128) / 128;
    sumSq += sample * sample;
  }
  const timeRms = Math.sqrt(sumSq / timeDomainData.length);

  if (!freqData || freqData.length === 0) {
    return Math.min(1, timeRms);
  }

  const nyquist = sampleRate / 2;
  const binHz = nyquist / freqData.length;
  const minBin = Math.max(1, Math.floor(250 / binHz));
  const maxBin = Math.min(freqData.length - 1, Math.ceil(3600 / binHz));

  let speechSum = 0;
  let totalSum = 0;
  for (let i = 1; i < freqData.length; i++) {
    const mag = freqData[i] / 255;
    totalSum += mag;
    if (i >= minBin && i <= maxBin) {
      speechSum += mag;
    }
  }

  if (totalSum <= 0.001) return Math.min(1, timeRms);
  const speechRatio = speechSum / totalSum;
  // Gate out non-vocal broadband/low-end noise if speech band has very low concentration
  const weight = speechRatio < 0.2 ? 0.5 : 1.0;
  return Math.min(1, timeRms * weight);
}

