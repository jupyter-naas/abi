import { describe, expect, it } from 'vitest';
import {
  SentenceAggregator,
  TEN_VAD_CONFIG,
  buildDomainVocabularyPrompt,
  KOKORO_MAX_CHARS,
  interruptedMessageContent,
  isNearDuplicateTranscript,
  spokenTextForTurn,
  transcriptSimilarity,
  callLanguageHint,
  callSpeechOptions,
  classifyTurnState,
  parseCallSettings,
  resolveCallLanguage,
  cleanSentenceForSpeech,
  computeSpeechBandRms,
  dominantScript,
  guessLatinLanguage,
  isBackchannelOnly,
  isForeignScriptNoise,
  isLikelyNoiseUtterance,
  isSilenceHallucination,
  judgeInterjection,
  scriptForLanguage,
  shouldCommitBargeIn,
} from './voice-call-engine';

describe('cleanSentenceForSpeech', () => {
  it('strips markdown formatting, links, and code blocks for natural TTS', () => {
    const raw =
      '### Summary\nCheck [Naas AI](https://naas.ai) and `uv run abi` with **bold** text.';
    expect(cleanSentenceForSpeech(raw)).toBe(
      'Summary Check Naas AI and uv run abi with bold text.',
    );
  });

  it('removes fenced code blocks and bare URLs', () => {
    const raw = 'Here is the snippet: ```python\nprint("hi")\n``` Visit https://example.com/docs now.';
    expect(cleanSentenceForSpeech(raw)).toBe('Here is the snippet: Visit now.');
  });
});

describe('SentenceAggregator', () => {
  it('splits streaming tokens into sentences as soon as punctuation + space arrives', () => {
    const agg = new SentenceAggregator();
    expect(agg.push('Hello there, how are ')).toEqual([]);
    expect(agg.push('you doing today? ')).toEqual(['Hello there, how are you doing today?']);
    expect(agg.push('I am doing great and ready to help.')).toEqual([]);
    expect(agg.flush()).toEqual(['I am doing great and ready to help.']);
  });

  it('does not split on abbreviations like Dr. or U.S. or decimals like 3.14', () => {
    const agg = new SentenceAggregator();
    const out1 = agg.push('Dr. Smith lives in the U.S. and pi is 3.14 in math. ');
    expect(out1).toEqual(['Dr. Smith lives in the U.S. and pi is 3.14 in math.']);
    expect(agg.flush()).toEqual([]);
  });

  it('uses the first-clause fast path on colon or semicolon when the opening clause is long', () => {
    const agg = new SentenceAggregator();
    const out = agg.push(
      'Here is the most important takeaway from the third quarter report: revenue grew by twenty percent.',
    );
    expect(out).toEqual([
      'Here is the most important takeaway from the third quarter report:',
    ]);
    expect(agg.flush()).toEqual(['revenue grew by twenty percent.']);
  });

  it('resets state cleanly on barge-in interruption', () => {
    const agg = new SentenceAggregator();
    agg.push('Partial sentence that gets interrupted');
    agg.reset();
    expect(agg.flush()).toEqual([]);
  });
});

describe('classifyTurnState (TEN Turn Detection)', () => {
  it('detects explicit wait / stop / hold commands in English and French', () => {
    expect(classifyTurnState('Stop')).toBe('wait');
    expect(classifyTurnState('Hold on a second.')).toBe('wait');
    expect(classifyTurnState('Give me a moment')).toBe('wait');
    expect(classifyTurnState('Attends une seconde')).toBe('wait');
    expect(classifyTurnState('Tais-toi')).toBe('wait');
    expect(classifyTurnState('Pause')).toBe('wait');
  });

  it('detects compound / embedded stop-talking utterances from live barge-ins', () => {
    expect(
      classifyTurnState(
        "No, I didn't even talk about TensorFlow. How about you just stop talking?",
      ),
    ).toBe('wait');
    expect(
      classifyTurnState(
        "Okay, that's too long, so I'm going to cut you off right now again. Okay, thank you. Let's just stop here.",
      ),
    ).toBe('wait');
    expect(classifyTurnState("C'est trop long, on arrête là s'il te plaît.")).toBe('wait');
  });

  it('builds domain vocabulary prompt with active agent name', () => {
    expect(buildDomainVocabularyPrompt('Bob')).toContain('Bob');
    expect(buildDomainVocabularyPrompt('Bob')).toContain('NaasAI');
    expect(buildDomainVocabularyPrompt('ABI')).toContain('ABI, NaasAI');
  });

  it('detects unfinished turns ending with conjunctions, prepositions, fillers, or ellipsis', () => {
    expect(classifyTurnState('I wanted to ask you about')).toBe('unfinished');
    expect(classifyTurnState('We should deploy the service because')).toBe('unfinished');
    expect(classifyTurnState('Let me think about the...')).toBe('unfinished');
    expect(classifyTurnState('So if we look at the.')).toBe('unfinished');
    expect(classifyTurnState('Je voudrais savoir si')).toBe('unfinished');
    expect(classifyTurnState('On doit vérifier parce que')).toBe('unfinished');
  });

  it('detects finished turns ready for immediate LLM response', () => {
    expect(classifyTurnState('What is the status of the Qdrant cluster?')).toBe('finished');
    expect(classifyTurnState('Tell me about our Q3 revenue numbers.')).toBe('finished');
    expect(classifyTurnState('Can you summarize the latest intelligence report?')).toBe(
      'finished',
    );
  });
});

describe('isBackchannelOnly & isSilenceHallucination', () => {
  it('recognizes short listener backchannels without triggering a floor-taking interruption', () => {
    expect(isBackchannelOnly('uh-huh')).toBe(true);
    expect(isBackchannelOnly('Okay.')).toBe(true);
    expect(isBackchannelOnly('Yeah')).toBe(true);
    expect(isBackchannelOnly("D'accord")).toBe(true);
    expect(isBackchannelOnly('Oui')).toBe(true);
    expect(isBackchannelOnly('Actually wait, change the slide title')).toBe(false);
  });

  it('filters out common Whisper silence hallucinations', () => {
    expect(isSilenceHallucination('')).toBe(true);
    expect(isSilenceHallucination('...')).toBe(true);
    expect(isSilenceHallucination('Thank you for watching.')).toBe(true);
    expect(isSilenceHallucination('Subtitles by')).toBe(true);
    expect(isSilenceHallucination('Hello ABI')).toBe(false);
  });

  it.each([
    '谢谢。',
    '谢谢观看',
    '請不吝點贊訂閱轉發打賞支持明鏡與點點欄目',
    '请不吝点赞 订阅 转发 打赏支持明镜与点点栏目',
    'ご視聴ありがとうございました',
    '¡Gracias!',
    'Merci.',
    'Sous-titrage Société Radio-Canada',
    'Sous-titres réalisés par la communauté d’Amara.org',
    'Untertitel im Auftrag des ZDF, 2021',
    'Thank you.',
    'Bye.',
    '♪ ♪',
    '♪♪♪',
    '[Music]',
    '?!…',
    ' - ',
  ])('drops the multilingual silence output %j', (text) => {
    expect(isSilenceHallucination(text)).toBe(true);
  });

  it('keeps real requests that merely contain thanks', () => {
    expect(isSilenceHallucination('Thank you, now summarize the report.')).toBe(false);
    expect(isSilenceHallucination('Merci, peux-tu ouvrir le tableau de bord ?')).toBe(false);
    expect(isSilenceHallucination('谢谢你，请总结一下这份报告的主要内容')).toBe(false);
  });
});

describe('script sanity check', () => {
  it('finds the dominant writing system', () => {
    expect(dominantScript('Bonjour Abi')).toBe('latin');
    expect(dominantScript('谢谢。')).toBe('cjk');
    expect(dominantScript('все')).toBe('cyrillic');
    expect(dominantScript('...')).toBeNull();
  });

  it('drops a short foreign-script transcript on a Latin-script call', () => {
    expect(isForeignScriptNoise('谢谢。', 'fr')).toBe(true);
    expect(isForeignScriptNoise('все', 'en')).toBe(true);
    expect(isForeignScriptNoise('谢谢。', null)).toBe(true);
    expect(isForeignScriptNoise('Bonjour', 'fr')).toBe(false);
  });

  it('keeps the expected script and long genuine switches', () => {
    expect(isForeignScriptNoise('谢谢', 'zh')).toBe(false);
    expect(isForeignScriptNoise('Hello', 'zh')).toBe(false);
    expect(
      isForeignScriptNoise('请帮我总结一下今天的会议记录并列出所有的行动项和负责人', 'en'),
    ).toBe(false);
    expect(scriptForLanguage('ja')).toBe('cjk');
    expect(scriptForLanguage('fr')).toBe('latin');
  });
});

describe('callLanguageHint', () => {
  it('prefers the language of recent user turns', () => {
    expect(callLanguageHint(['Bonjour, je veux que tu ouvres le tableau'], 'en-US')).toBe('fr');
    expect(callLanguageHint(['Can you open the dashboard please'], 'fr-FR')).toBe('en');
  });

  it('falls back to the browser language when turns are unclear', () => {
    expect(callLanguageHint([], 'fr-FR')).toBe('fr');
    expect(callLanguageHint(['OK'], 'de')).toBe('de');
    expect(callLanguageHint([], undefined)).toBeNull();
    expect(guessLatinLanguage('Hi')).toBeNull();
  });
});

describe('judgeInterjection', () => {
  it('lets the reply continue over noise, hallucinations and backchannels', () => {
    expect(judgeInterjection('', 'en')).toBe('drop');
    expect(judgeInterjection('谢谢。', 'fr')).toBe('drop');
    expect(judgeInterjection('Thank you.', 'en')).toBe('drop');
    expect(judgeInterjection('uh-huh', 'en')).toBe('drop');
    expect(judgeInterjection("D'accord", 'fr')).toBe('drop');
    expect(judgeInterjection('♪', 'en')).toBe('drop');
  });

  it('takes the floor for a real request or an explicit stop', () => {
    expect(judgeInterjection('Actually, look up SpaceX instead.', 'en')).toBe('interrupt');
    expect(judgeInterjection('Stop talking', 'en')).toBe('interrupt');
    expect(judgeInterjection('Attends, change de sujet', 'fr')).toBe('interrupt');
  });
});

describe('isLikelyNoiseUtterance', () => {
  it('drops clips that are too short or too faint to be speech', () => {
    expect(isLikelyNoiseUtterance({ voicedMs: 80, avgVoicedRms: 0.2 })).toBe(true);
    expect(isLikelyNoiseUtterance({ voicedMs: 900, avgVoicedRms: 0.024 })).toBe(true);
  });

  it('commits a barge-in only after a sustained, speech-like burst', () => {
    const commit = TEN_VAD_CONFIG.BARGE_IN_COMMIT_MS;
    expect(shouldCommitBargeIn({ voicedMs: commit - 16, avgVoicedRms: 0.2 })).toBe(false);
    expect(shouldCommitBargeIn({ voicedMs: commit, avgVoicedRms: 0.01 })).toBe(false);
    expect(shouldCommitBargeIn({ voicedMs: commit, avgVoicedRms: 0.08 })).toBe(true);
  });

  it('keeps a normal spoken turn', () => {
    expect(
      isLikelyNoiseUtterance({
        voicedMs: TEN_VAD_CONFIG.MIN_VOICED_MS + 400,
        avgVoicedRms: TEN_VAD_CONFIG.MIN_AVG_VOICED_RMS + 0.04,
      }),
    ).toBe(false);
  });
});

describe('TEN_VAD_CONFIG & computeSpeechBandRms', () => {
  it('exposes TEN-VAD 16ms hop and turn-taking thresholds', () => {
    expect(TEN_VAD_CONFIG.HOP_INTERVAL_MS).toBe(16);
    expect(TEN_VAD_CONFIG.DUCKING_HOLD_MS).toBeLessThan(TEN_VAD_CONFIG.BARGE_IN_COMMIT_MS);
    expect(TEN_VAD_CONFIG.FINISHED_SILENCE_MS).toBeLessThan(TEN_VAD_CONFIG.UNFINISHED_WAIT_MS);
  });

  it('returns 0 RMS for silence centered at 128', () => {
    const silent = new Uint8Array(512).fill(128);
    expect(computeSpeechBandRms(silent)).toBeCloseTo(0, 4);
  });
});

describe('call settings', () => {
  it('falls back to defaults for missing or unknown values', () => {
    expect(parseCallSettings(null)).toEqual({ language: 'auto', voice: '', inputDeviceId: '' });
    expect(parseCallSettings('not json')).toEqual({ language: 'auto', voice: '', inputDeviceId: '' });
    expect(parseCallSettings('{"language":"de","voice":"nope","inputDeviceId":"mic-1"}')).toEqual({
      language: 'auto',
      voice: '',
      inputDeviceId: 'mic-1',
    });
    expect(parseCallSettings('{"language":"fr","voice":"am_michael"}').language).toBe('fr');
  });

  it('lets a chosen language override the guess from recent turns', () => {
    expect(resolveCallLanguage('fr', ['hello there, how are you'], 'en-US')).toBe('fr');
    expect(resolveCallLanguage('auto', [], 'fr-FR')).toBe('fr');
  });

  it('sends a voice only for English sentences Kokoro speaks', () => {
    expect(callSpeechOptions({ language: 'auto', voice: 'am_michael' }, 40)).toEqual({});
    expect(callSpeechOptions({ language: 'en', voice: 'am_michael' }, 40)).toEqual({
      language: 'en',
      voice: 'am_michael',
    });
    expect(callSpeechOptions({ language: 'en', voice: 'am_michael' }, KOKORO_MAX_CHARS)).toEqual({
      language: 'en',
    });
    expect(callSpeechOptions({ language: 'fr', voice: 'am_michael' }, 40)).toEqual({ language: 'fr' });
  });
});

describe('repeat transcripts', () => {
  // Three transcriptions of one utterance, 0.4 s apart (conv-f6w4mex5c4n).
  const first = { text: 'Je sais pas trop quoi penser de ce design.', at: 1_000 };

  it('drops look-alikes of the last transcript that arrive within a second', () => {
    expect(isNearDuplicateTranscript(first, 'Pas trop quoi penser du ce design.', 1_200)).toBe(true);
    expect(isNearDuplicateTranscript(first, 'Alors quoi penser du C-Design?', 1_400)).toBe(true);
  });

  it('keeps a different sentence, or the same one said again later', () => {
    expect(isNearDuplicateTranscript(first, 'Et pour Tesla, tu as les chiffres ?', 1_200)).toBe(false);
    expect(isNearDuplicateTranscript(first, first.text, 4_000)).toBe(false);
    expect(isNearDuplicateTranscript(null, first.text, 1_000)).toBe(false);
  });

  it('ignores case, accents and punctuation', () => {
    expect(transcriptSimilarity('Très bien !', 'tres bien')).toBe(1);
    expect(transcriptSimilarity('', 'oui')).toBe(0);
  });
});

describe('spoken text per turn', () => {
  const spoken = [
    { turnId: 1, text: 'Mercury is closest to the sun.' },
    { turnId: 2, text: 'Hello Alex.' },
  ];

  it('uses only the interrupted turn’s sentences', () => {
    expect(spokenTextForTurn(spoken, 2, { turnId: 2, text: 'Venus is hot.' })).toBe(
      'Hello Alex. Venus is hot.',
    );
    expect(spokenTextForTurn(spoken, 1, { turnId: 2, text: 'Venus is hot.' })).toBe(
      'Mercury is closest to the sun.',
    );
    expect(spokenTextForTurn(spoken, 3, null)).toBe('');
  });

  it('marks the bubble once, with what was heard before what had streamed', () => {
    expect(interruptedMessageContent('Hello Alex.', 'Hello Alex. And more▌')).toBe(
      'Hello Alex. … [interrupted]',
    );
    expect(interruptedMessageContent('', 'Streamed so far▌')).toBe('Streamed so far … [interrupted]');
    expect(interruptedMessageContent('x', 'Done … [interrupted]')).toBe('Done … [interrupted]');
  });
});
