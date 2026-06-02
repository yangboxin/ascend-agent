/**
 * ANSI escape sequence utilities.
 *
 * Low-level helpers for SGR codes, cursor movement, and screen control.
 */

const ESC = '\x1b';

/** Build a Select Graphic Rendition (SGR) escape sequence. */
export function sgr(...codes: number[]): string {
  if (codes.length === 0) codes = [0];
  return `${ESC}[${codes.join(';')}m`;
}

/** SGR reset — clears all attributes. */
export function reset(): string {
  return sgr(0);
}

// Common SGR codes
export const SGR = {
  RESET: 0,
  BOLD: 1,
  DIM: 2,
  ITALIC: 3,
  UNDERLINE: 4,
  FG_BLACK: 30,
  FG_RED: 31,
  FG_GREEN: 32,
  FG_YELLOW: 33,
  FG_BLUE: 34,
  FG_MAGENTA: 35,
  FG_CYAN: 36,
  FG_WHITE: 37,
  BG_BLACK: 40,
  BG_RED: 41,
  BG_GREEN: 42,
  BG_YELLOW: 43,
  BG_BLUE: 44,
  BG_MAGENTA: 45,
  BG_CYAN: 46,
  BG_WHITE: 47,
} as const;

/** Move cursor up n rows. */
export function cursorUp(n = 1): string {
  return `${ESC}[${n}A`;
}

/** Move cursor down n rows. */
export function cursorDown(n = 1): string {
  return `${ESC}[${n}B`;
}

/** Erase current line. */
export function eraseLine(mode = 2): string {
  return `${ESC}[${mode}K`;
}

/** Erase display. */
export function eraseDisplay(mode = 2): string {
  return `${ESC}[${mode}J`;
}

// Regex for stripping ANSI escapes
const ANSI_RE = /\x1b\[[0-?]*[ -/]*[@-~]/g;

/** Remove all ANSI escape sequences from text. */
export function stripAnsi(text: string): string {
  return text.replace(ANSI_RE, '');
}

/** Return the visible column width of text (minus ANSI escapes). */
export function visibleWidth(text: string): number {
  return stripAnsi(text).length;
}
