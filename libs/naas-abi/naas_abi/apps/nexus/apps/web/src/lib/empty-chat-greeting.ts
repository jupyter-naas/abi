import { isSlidesAgent, type SlidesAgentPick } from './create-slides-project';

export const SLIDES_EMPTY_GREETING_SUFFIX =
  'This is a Minimal Light deck. Tell me the topic and I will write the slides.';

export const SLIDES_COMPOSER_PLACEHOLDER =
  'Describe the deck: topic, audience, how many slides...';

export const DEFAULT_COMPOSER_PLACEHOLDER = 'Send a message...';

/** Empty-state slides copy is SlidesAgent-only. A persisted deck slug must not leak it. */
export function showSlidesEmptyCopy(agent?: SlidesAgentPick | null): boolean {
  return Boolean(agent && isSlidesAgent(agent));
}

export function emptyChatGreeting(
  firstName: string | undefined,
  agentName: string,
  agent?: SlidesAgentPick | null,
): string {
  const hello = firstName?.trim() ? `Hello, ${firstName.trim()}.` : 'Hello.';
  if (showSlidesEmptyCopy(agent)) {
    return `${hello} ${SLIDES_EMPTY_GREETING_SUFFIX}`;
  }
  return `${hello} ${agentName} here, how can I help?`;
}

export function emptyChatPlaceholder(agent?: SlidesAgentPick | null): string {
  return showSlidesEmptyCopy(agent)
    ? SLIDES_COMPOSER_PLACEHOLDER
    : DEFAULT_COMPOSER_PLACEHOLDER;
}
