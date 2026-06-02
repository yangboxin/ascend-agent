/**
 * Hook: monitor terminal resize events.
 *
 * Provides reactive terminal size tracking so components adapt
 * their layout when the user resizes the terminal window.
 */

import { useState, useEffect } from 'react';
import { useStdout } from 'ink';

export interface TerminalSize {
  columns: number;
  rows: number;
}

export function useTerminalSize(): TerminalSize {
  const { stdout } = useStdout();
  const [size, setSize] = useState<TerminalSize>(() => ({
    columns: stdout?.columns ?? 80,
    rows: stdout?.rows ?? 24,
  }));

  useEffect(() => {
    if (!stdout) return;

    const handler = () => {
      setSize({
        columns: stdout.columns ?? 80,
        rows: stdout.rows ?? 24,
      });
    };

    stdout.on('resize', handler);
    return () => {
      stdout.off('resize', handler);
    };
  }, [stdout]);

  return size;
}

/** Calculate height available for content area (minus input + status). */
export function contentHeight(size: TerminalSize): number {
  return Math.max(1, size.rows - 5); // 3 input + 1 status + 1 separator
}
