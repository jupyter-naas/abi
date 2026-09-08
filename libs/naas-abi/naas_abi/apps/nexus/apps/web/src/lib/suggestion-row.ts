/** Nav state for a single-line suggestion scroller. */

export type ChatSuggestion = {
  label: string;
  value: string;
  description?: string;
  disabled?: boolean;
  cta?: string;
};

/** Active suggestions only. Drop grayed / coming-soon items. */
export function activeSuggestions<T extends { disabled?: boolean }>(
  suggestions: T[] | undefined | null,
): T[] {
  if (!Array.isArray(suggestions)) return [];
  return suggestions.filter((suggestion) => !suggestion.disabled);
}

/** One-line hint under the suggestion name. Prefer description; else the prompt. */
export function suggestionHint(suggestion: {
  description?: string;
  value: string;
}): string {
  const description = suggestion.description?.trim();
  if (description) return description.replace(/\s+/g, ' ');
  const firstLine = suggestion.value.trim().split(/\r?\n/)[0] ?? '';
  return firstLine.replace(/\s+/g, ' ');
}

export function suggestionRowNavState(
  scrollLeft: number,
  clientWidth: number,
  scrollWidth: number,
): { overflow: boolean; canPrev: boolean; canNext: boolean } {
  const overflow = scrollWidth > clientWidth + 2;
  return {
    overflow,
    canPrev: overflow && scrollLeft > 1,
    canNext: overflow && scrollLeft + clientWidth < scrollWidth - 1,
  };
}

export function suggestionScrollStep(clientWidth: number): number {
  return Math.max(160, Math.floor(clientWidth * 0.75));
}
