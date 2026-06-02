/**
 * Hook: command history management.
 *
 * Provides Up/Down arrow navigation through previously entered commands,
 * with duplicate suppression and optional disk persistence.
 */

import { useState, useCallback, useRef } from 'react';

const MAX_HISTORY = 500;

export interface CommandHistory {
  /** All history entries (most recent last). */
  entries: string[];
  /** Add a command to history (skips consecutive duplicates). */
  add: (cmd: string) => void;
  /** Navigate up (older) — returns the historical command or null. */
  navigateUp: (currentInput: string) => string | null;
  /** Navigate down (newer) — returns the historical command, or the pre-nav input, or null. */
  navigateDown: () => string | null;
  /** Clear all history. */
  clear: () => void;
  /** Search history by prefix. */
  search: (prefix: string) => string[];
}

export function useCommandHistory(): CommandHistory {
  const [entries, setEntries] = useState<string[]>([]);
  const indexRef = useRef(-1);
  const savedInputRef = useRef('');

  const add = useCallback((cmd: string) => {
    const trimmed = cmd.trim();
    if (!trimmed) return;
    setEntries(prev => {
      // Suppress consecutive duplicates
      if (prev.length > 0 && prev[prev.length - 1] === trimmed) return prev;
      const next = [...prev, trimmed];
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
    });
    indexRef.current = -1;
    savedInputRef.current = '';
  }, []);

  const navigateUp = useCallback((currentInput: string): string | null => {
    if (entries.length === 0) return null;
    if (indexRef.current === -1) {
      savedInputRef.current = currentInput;
      indexRef.current = entries.length - 1;
    } else if (indexRef.current > 0) {
      indexRef.current--;
    } else {
      return null; // Already at oldest
    }
    return entries[indexRef.current];
  }, [entries]);

  const navigateDown = useCallback((): string | null => {
    if (indexRef.current === -1) return null;
    if (indexRef.current < entries.length - 1) {
      indexRef.current++;
      return entries[indexRef.current];
    }
    // Return to the pre-navigation input
    indexRef.current = -1;
    const saved = savedInputRef.current;
    savedInputRef.current = '';
    return saved;
  }, [entries]);

  const clear = useCallback(() => {
    setEntries([]);
    indexRef.current = -1;
    savedInputRef.current = '';
  }, []);

  const search = useCallback((prefix: string): string[] => {
    const lower = prefix.toLowerCase();
    return entries.filter(e => e.toLowerCase().startsWith(lower));
  }, [entries]);

  return { entries, add, navigateUp, navigateDown, clear, search };
}
