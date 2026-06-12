import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge Tailwind classes with clsx — handles conflicts correctly */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
