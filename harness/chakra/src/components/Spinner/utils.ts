import type { RGBColor as RGBColorString } from '../../ink/styles.js'
import sample from 'lodash-es/sample.js'
import type { RGBColor as RGBColorType } from './types.js'

/**
 * Full animation cycle: forward then reverse (legacy ping-pong). Prefer
 * {@link pickRandomSpinnerFrames} for rattles-style presets (forward loops).
 */
export function buildPingPongFrames(forward: readonly string[]): string[] {
  if (forward.length === 0) {
    return ['·']
  }
  if (forward.length === 1) {
    return [forward[0]!]
  }
  const rev = [...forward].reverse()
  return [...forward, ...rev]
}

/**
 * Frame arrays adapted from rattles (braille + ascii presets) — each array is
 * one full forward loop. https://github.com/vyfor/rattles
 */
const SPINNER_PRESETS: readonly (readonly string[])[] = [
  // Braille — Dots, Dots2, Dots3, …
  ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
  ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'],
  ['⠋', '⠙', '⠚', '⠞', '⠖', '⠦', '⠴', '⠲', '⠳', '⠓'],
  [
    '⠄', '⠆', '⠇', '⠋', '⠙', '⠸', '⠰', '⠠', '⠰', '⠸', '⠙', '⠋', '⠇', '⠆',
  ],
  [
    '⠋', '⠙', '⠚', '⠒', '⠂', '⠂', '⠒', '⠲', '⠴', '⠦', '⠖', '⠒', '⠐', '⠐', '⠒', '⠓', '⠋',
  ],
  [
    '⠁', '⠉', '⠙', '⠚', '⠒', '⠂', '⠂', '⠒', '⠲', '⠴', '⠤', '⠄', '⠄', '⠤', '⠴', '⠲', '⠒', '⠂',
    '⠂', '⠒', '⠚', '⠙', '⠉', '⠁',
  ],
  [
    '⠈', '⠉', '⠋', '⠓', '⠒', '⠐', '⠐', '⠒', '⠖', '⠦', '⠤', '⠠', '⠠', '⠤', '⠦', '⠖', '⠒', '⠐',
    '⠐', '⠒', '⠓', '⠋', '⠉', '⠈',
  ],
  [
    '⠁', '⠁', '⠉', '⠙', '⠚', '⠒', '⠂', '⠂', '⠒', '⠲', '⠴', '⠤', '⠄', '⠄', '⠤', '⠠', '⠠', '⠤',
    '⠦', '⠖', '⠒', '⠐', '⠐', '⠒', '⠓', '⠋', '⠉', '⠈', '⠈',
  ],
  ['⢹', '⢺', '⢼', '⣸', '⣇', '⡧', '⡗', '⡏'],
  ['⢄', '⢂', '⢁', '⡁', '⡈', '⡐', '⡠'],
  ['⠁', '⠂', '⠄', '⡀', '⢀', '⠠', '⠐', '⠈'],
  [
    '⠁', '⠂', '⠄', '⡀', '⡈', '⡐', '⡠', '⣀', '⣁', '⣂', '⣄', '⣌', '⣔', '⣤', '⣥', '⣦', '⣮', '⣶',
    '⣷', '⣿', '⡿', '⠿', '⢟', '⠟', '⡛', '⠛', '⠫', '⢋', '⠋', '⠍', '⡉', '⠉', '⠑', '⠡', '⢁',
  ],
  ['⠁', '⠂', '⠄', '⡀', '⠄', '⠂'],
  ['⢎ ', '⠎⠁', '⠊⠑', '⠈⠱', ' ⡱', '⢀⡰', '⢄⡠', '⢆⡀'],
  ['⠃', '⠉', '⠘', '⠰', '⢠', '⣀', '⡄', '⠆'],
  [
    '⠀', '⠂', '⠌', '⡑', '⢕', '⢝', '⣫', '⣟', '⣿', '⣟', '⣫', '⢝', '⢕', '⡑', '⠌', '⠂', '⠀',
  ],
  ['⣼', '⣹', '⢻', '⠿', '⡟', '⣏', '⣧', '⣶'],
  [
    '⠉⠉', '⠈⠙', '⠀⠹', '⠀⢸', '⠀⣰', '⢀⣠', '⣀⣀', '⣄⡀', '⣆⠀', '⡇⠀', '⠏⠀', '⠋⠁',
  ],
  [
    '⣀⣀', '⣤⣤', '⣶⣶', '⣿⣿', '⣿⣿', '⣿⣿', '⣶⣶', '⣤⣤', '⣀⣀', '⠀⠀', '⠀⠀',
  ],
  [
    '⠁⠀', '⠋⠀', '⠟⠁', '⡿⠋', '⣿⠟', '⣿⡿', '⣿⣿', '⣿⣿', '⣾⣿', '⣴⣿', '⣠⣾', '⢀⣴', '⠀⣠', '⠀⢀', '⠀⠀',
    '⠀⠀',
  ],
  // ASCII / symbols
  ['d', 'q', 'p', 'b'],
  ['/', '-', '\\', '|', '\\', '-'],
  ['.  ', '.. ', '...', '   '],
  ['.  ', '.. ', '...', ' ..', '  .', '   '],
  ['◜', '◠', '◝', '◞', '◡', '◟'],
  ['.', 'o', 'O', 'o', '.'],
  ['◐', '◓', '◑', '◒'],
  ['◴', '◷', '◶', '◵'],
  ['···', '•··', '·•·', '··•', '···'],
  ['◰', '◳', '◲', '◱'],
  ['⊶', '⊷'],
  ['◢', '◣', '◤', '◥'],
  ['▏', '▎', '▍', '▌', '▋', '▊', '▉', '▊', '▋', '▌', '▍', '▎'],
  ['▁', '▃', '▄', '▅', '▆', '▇', '▆', '▅', '▄', '▃'],
  ['▓', '▒', '░', ' ', '░', '▒'],
]

function adaptPatternForTerminal(pattern: readonly string[]): string[] {
  const copy = [...pattern]
  if (process.env.TERM === 'xterm-ghostty') {
    return copy.map(g => g.replaceAll('✽', '*'))
  }
  return copy
}

/** One full forward animation cycle, picked at random (stable per React useMemo + session key). */
export function pickRandomSpinnerFrames(): string[] {
  const picked = sample([...SPINNER_PRESETS]) ?? [...SPINNER_PRESETS[0]!]
  return adaptPatternForTerminal(picked)
}

/** Stable frames when no session (e.g. /btw, standalone Spinner). */
export const FALLBACK_SPINNER_FRAMES: string[] = [...(SPINNER_PRESETS[0] ?? ['⠋', '⠙', '⠹'])]

/**
 * @deprecated Use {@link pickRandomSpinnerFrames} for wait UI. Kept for callers
 * that still import this symbol.
 */
export function getDefaultCharacters(): string[] {
  return [...(SPINNER_PRESETS[0] ?? ['⠋', '⠙', '⠹'])]
}

export function interpolateColor(
  color1: RGBColorType,
  color2: RGBColorType,
  t: number, // 0 to 1
): RGBColorType {
  return {
    r: Math.round(color1.r + (color2.r - color1.r) * t),
    g: Math.round(color1.g + (color2.g - color1.g) * t),
    b: Math.round(color1.b + (color2.b - color1.b) * t),
  }
}

export function toRGBColor(color: RGBColorType): RGBColorString {
  return `rgb(${color.r},${color.g},${color.b})`
}

export function hueToRgb(hue: number): RGBColorType {
  const h = ((hue % 360) + 360) % 360
  const s = 0.7
  const l = 0.6
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = l - c / 2
  let r = 0
  let g = 0
  let b = 0
  if (h < 60) {
    r = c
    g = x
  } else if (h < 120) {
    r = x
    g = c
  } else if (h < 180) {
    g = c
    b = x
  } else if (h < 240) {
    g = x
    b = c
  } else if (h < 300) {
    r = x
    b = c
  } else {
    r = c
    b = x
  }
  return {
    r: Math.round((r + m) * 255),
    g: Math.round((g + m) * 255),
    b: Math.round((b + m) * 255),
  }
}

export function parseRGB(rgb: string): RGBColorType | null {
  const m = /^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/.exec(rgb.trim())
  if (!m) {
    return null
  }
  return {
    r: Number(m[1]),
    g: Number(m[2]),
    b: Number(m[3]),
  }
}
