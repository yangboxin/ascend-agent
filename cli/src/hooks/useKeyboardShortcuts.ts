/**
 * Hook: keyboard shortcut handler.
 *
 * Defines all keyboard shortcuts for the TUI application:
 * - Ctrl+C: interrupt current operation (does NOT exit)
 * - Ctrl+D: quit application (on empty input)
 * - Ctrl+L: clear screen
 * - Up/Down: navigate command history
 * - Escape: cancel current operation
 */

import { useInput } from 'ink';

export interface KeyboardHandlers {
  onInterrupt: () => void;
  onQuit: () => void;
  onClear: () => void;
  onHistoryUp: () => void;
  onHistoryDown: () => void;
  onCancel: () => void;
}

export function useKeyboardShortcuts(handlers: KeyboardHandlers) {
  useInput((input, key) => {
    // Ctrl+C — interrupt current operation
    if (key.ctrl && input === 'c') {
      handlers.onInterrupt();
      return;
    }

    // Ctrl+D — quit on empty input (handled by InputBar)
    if (key.ctrl && input === 'd') {
      handlers.onQuit();
      return;
    }

    // Ctrl+L — clear screen
    if (key.ctrl && input === 'l') {
      handlers.onClear();
      return;
    }

    // Escape — cancel
    if (key.escape) {
      handlers.onCancel();
      return;
    }

    // Up arrow — history backward
    if (key.upArrow) {
      handlers.onHistoryUp();
      return;
    }

    // Down arrow — history forward
    if (key.downArrow) {
      handlers.onHistoryDown();
      return;
    }
  });
}
