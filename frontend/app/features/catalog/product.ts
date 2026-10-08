export function clampQuantity(value: string, available: number): number {
  if (available <= 0) return 0;
  const requested = Number(value);
  if (!Number.isSafeInteger(requested)) return 1;
  return Math.min(Math.max(requested, 1), available);
}

/** Manual gallery controls wrap in staff-defined image order. */
export function galleryImageIndex(current: number, direction: number, count: number): number {
  if (count <= 1) return 0;
  return ((current + direction) % count + count) % count;
}
