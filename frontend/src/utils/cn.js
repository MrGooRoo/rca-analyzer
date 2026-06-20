/**
 * Merge class names — simple utility, no external dependencies.
 * Filters falsy values and joins with space.
 */
export function cn(...inputs) {
  return inputs.filter(Boolean).join(' ')
}