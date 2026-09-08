/** Slides pane empty-state copy. Names the bound agent, never a guessed template. */

export function slidesEmptyStateCopy(opts: {
  firstName?: string | null;
  agentName?: string | null;
  templateName?: string | null;
}): string {
  const first = (opts.firstName || '').trim();
  const greeting = first ? `Hello, ${first}.` : 'Hello.';
  const agent = (opts.agentName || '').trim();
  const who = agent ? `I am ${agent}.` : '';
  const template = (opts.templateName || '').trim();
  const about = template ? `This is a ${template} deck.` : '';
  const ask = 'Tell me the topic and I will write the slides.';
  return [greeting, who, about, ask].filter(Boolean).join(' ');
}
