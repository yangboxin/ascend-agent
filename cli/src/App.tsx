/**
 * App.tsx — Root component for the Ascend Agent TUI.
 *
 * Wires together all components into a Claude Code-like immersive
 * terminal experience with:
 * - Full-screen alternate buffer (handled by Ink)
 * - Fixed-bottom input bar
 * - Scrollable content area
 * - Status line
 * - Keyboard shortcuts
 * - Streaming response support
 */

import React, { useState, useCallback, useRef } from 'react';
import { Box } from 'ink';
import { ContentArea } from './components/ContentArea.js';
import { InputBar } from './components/InputBar.js';
import { StatusLine } from './components/StatusLine.js';
import { Message, createMessage } from './components/MessageBubble.js';
import { useTerminalSize } from './hooks/useTerminalSize.js';
import { useCommandHistory } from './hooks/useCommandHistory.js';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts.js';
import { useStreamingResponse } from './hooks/useStreamingResponse.js';

interface AppProps {
  provider: string;
  model: string;
  onUserInput?: (text: string) => Promise<void>;
  onQuit?: () => void;
}

export const App: React.FC<AppProps> = ({
  provider: initialProvider,
  model: initialModel,
  onUserInput,
  onQuit,
}) => {
  // --- State ---
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [provider] = useState(initialProvider);
  const [model] = useState(initialModel);
  const [isStreaming, setIsStreaming] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // --- Terminal size ---
  const size = useTerminalSize();

  // --- Command history ---
  const history = useCommandHistory();

  // --- Streaming ---
  const stream = useStreamingResponse(
    useCallback((chunk: string) => {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'assistant') {
          return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
        }
        return [...prev, createMessage('assistant', chunk)];
      });
    }, []),
    useCallback(() => {
      setIsStreaming(false);
    }, []),
    useCallback((error: Error) => {
      setMessages(prev => [...prev, createMessage('system', `Stream error: ${error.message}`)]);
      setIsStreaming(false);
    }, []),
  );

  // Timer for streaming elapsed
  React.useEffect(() => {
    if (!stream.streamState.isStreaming) return;
    const interval = setInterval(() => {
      setElapsed((Date.now() - (stream as any)._startTime) / 1000 || 0);
    }, 100);
    return () => clearInterval(interval);
  }, [stream.streamState.isStreaming]);

  // --- Input handler ---
  const handleSubmit = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    // Add to history
    history.add(trimmed);

    // Handle slash commands
    if (trimmed.startsWith('/')) {
      handleSlashCommand(trimmed);
      setInput('');
      return;
    }

    // Add user message
    const userMsg = createMessage('user', trimmed);
    setMessages(prev => [...prev, userMsg]);

    // Call the external handler for AI response
    if (onUserInput) {
      try {
        await onUserInput(trimmed);
      } catch (e: any) {
        setMessages(prev => [...prev, createMessage('system', `Error: ${e.message}`)]);
      }
    }

    setInput('');
  }, [history, onUserInput]);

  // --- Slash command handler ---
  const handleSlashCommand = useCallback((text: string) => {
    const parts = text.split(/\s+/);
    const cmd = parts[0].slice(1).toLowerCase();

    switch (cmd) {
      case 'quit':
      case 'exit':
      case 'q':
        onQuit?.();
        break;
      case 'help':
        setMessages(prev => [...prev, createMessage('system',
          `Available Commands

  /models          Show current model and available model IDs
  /models use <id> Select a model
  /chat <message>  Chat with the active LLM provider
  /reset-chat      Clear chat history
  /help            Show this help
  /quit            Exit the session
  /exit            Same as /quit

Keyboard shortcuts:
  Ctrl+C  Interrupt current operation
  Ctrl+D  Quit application
  Ctrl+L  Clear screen
  ↑/↓     Browse command history
  Esc     Cancel current operation`
        )]);
        break;
      case 'reset-chat':
        setMessages([]);
        setMessages([createMessage('system', ' Chat history cleared.')]);
        break;
      case 'models':
        setMessages(prev => [...prev, createMessage('system',
          `Active model: ${model || 'unknown'}
Use /models use <id> to switch models.`
        )]);
        break;
      default:
        setMessages(prev => [...prev, createMessage('system',
          `Unknown command: /${cmd}
Type /help for available commands.`
        )]);
    }
  }, [model, onQuit]);

  // --- Keyboard shortcuts ---
  useKeyboardShortcuts({
    onInterrupt: useCallback(() => {
      if (stream.streamState.isStreaming) {
        stream.requestInterrupt();
        setMessages(prev => [...prev, createMessage('system', ' [Interrupted]')]);
      } else {
        setInput('');
      }
    }, [stream]),
    onQuit: useCallback(() => {
      onQuit?.();
    }, [onQuit]),
    onClear: useCallback(() => {
      setMessages([]);
    }, []),
    onHistoryUp: useCallback(() => {
      const prev = history.navigateUp(input);
      if (prev !== null) setInput(prev);
    }, [history, input]),
    onHistoryDown: useCallback(() => {
      const next = history.navigateDown();
      if (next !== null) setInput(next);
    }, [history]),
    onCancel: useCallback(() => {
      if (stream.streamState.isStreaming) {
        stream.requestInterrupt();
      } else {
        setInput('');
      }
    }, [stream]),
  });

  // --- Layout ---
  return (
    <Box flexDirection="column" height={size.rows} width={size.columns}>
      {/* Status bar */}
      <StatusLine
        provider={provider}
        model={model}
        isStreaming={stream.streamState.isStreaming}
        tokenCount={stream.streamState.totalChars}
        elapsed={stream.streamState.elapsed || elapsed}
        width={size.columns}
      />

      {/* Scrollable content area */}
      <ContentArea
        messages={messages}
        width={size.columns}
        height={size.rows - 5}
      />

      {/* Fixed bottom input */}
      <InputBar
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
      />
    </Box>
  );
};
