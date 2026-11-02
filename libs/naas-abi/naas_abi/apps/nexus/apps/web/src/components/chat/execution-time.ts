/** Seconds from `sentAt` (epoch ms) to `now`, or undefined when the send time is unknown. */
export function elapsedSecondsSince(
  sentAt: number | null | undefined,
  now: number = Date.now(),
): number | undefined {
  if (!sentAt || now < sentAt) return undefined;
  return (now - sentAt) / 1000;
}
