/**
 * Terminal control utilities — alternate screen buffer, ANSI escapes.
 *
 * Handles full-screen mode entry/exit (alternate screen buffer),
 * analogous to vim/less/htop.
 */

/** Enter the alternate screen buffer (full-screen mode). */
export function enterAlternateScreen(): void {
  process.stdout.write('\x1b[?1049h'); // Switch to alternate screen
  process.stdout.write('\x1b[?25l');   // Hide cursor
}

/** Restore the main screen buffer. */
export function exitAlternateScreen(): void {
  process.stdout.write('\x1b[?25h');   // Show cursor
  process.stdout.write('\x1b[?1049l'); // Restore main screen
}

/** Get current terminal size as [columns, rows]. */
export function getTerminalSize(): [number, number] {
  return [process.stdout.columns ?? 80, process.stdout.rows ?? 24];
}

/** Check if stdout is a TTY. */
export function isTerminal(): boolean {
  return process.stdout.isTTY ?? false;
}

/** Check if terminal supports truecolor. */
export function supportsTrueColor(): boolean {
  const ct = process.env.COLORTERM ?? '';
  if (ct === 'truecolor' || ct === '24bit') return true;
  const term = process.env.TERM ?? '';
  return term.includes('256color') || term.includes('truecolor');
}
