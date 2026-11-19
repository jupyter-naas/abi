/**
 * Upload by drop on the Files page: when a drag really leaves the drop zone, and
 * whether it carries files from the computer.
 */

/** A `dragleave` counts only when the drag goes outside the zone (or the window). */
export function leavesDropZone(zone: Node, relatedTarget: EventTarget | null): boolean {
  return !(relatedTarget instanceof Node && zone.contains(relatedTarget));
}

/** Files dragged from the computer (not a row moved within the page). */
export function carriesExternalFiles(types: readonly string[]): boolean {
  return types.includes('Files');
}
