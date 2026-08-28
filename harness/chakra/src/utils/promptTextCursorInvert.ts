import chalk from 'chalk'

/** Cursor cell: white background, dark glyph — readable on dark prompt surfaces. */
export function promptTextCursorInvert(text: string): string {
  return chalk.bgRgb(255, 255, 255).rgb(62, 62, 82)(text)
}
