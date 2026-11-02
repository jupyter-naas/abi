/**
 * Apply `update` to the message with `messageId`, or to the last message when
 * no id is known yet. An id that is no longer in the list changes nothing:
 * a finished or aborted stream must not write into a newer turn's bubble.
 */
export function updateMessageInList<M extends { id: string }>(
  messages: M[],
  messageId: string | null | undefined,
  update: (message: M) => M,
): M[] {
  const index = messageId
    ? messages.findIndex((m) => m.id === messageId)
    : messages.length - 1;
  if (index < 0) return messages;
  return messages.map((m, i) => (i === index ? update(m) : m));
}
