/** Nav state for a single-line suggestion scroller. */

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
