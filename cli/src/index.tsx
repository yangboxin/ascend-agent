#!/usr/bin/env node
/**
 * CLI entry point — Ascend Standard Diagnostic TUI.
 *
 * Launches the immersive full-screen terminal interface using Ink + React.
 *
 * Usage:
 *   asd                          # Launch the TUI (default, auto-detect TTY)
 *   asd --provider openai        # Use a specific LLM provider
 *   asd --model gpt-5.5          # Use a specific model
 *   asd --no-tui                 # Use simple REPL instead of TUI
 */

import React from 'react';
import { render } from 'ink';
import { program } from 'commander';
import { App } from './App.js';
import { isTerminal } from './utils/terminal.js';

// Resolve provider/model from env or config
function resolveProvider(): string {
  return process.env.ASCEND_PROVIDER ?? 'openai';
}

function resolveModel(): string {
  return process.env.ASCEND_MODEL ?? '';
}

// ---- CLI Configuration ----

program
  .name('asd')
  .description('Ascend Standard Diagnostic — immersive terminal interface')
  .version('0.1.0')
  .option('-p, --provider <name>', 'LLM provider (e.g., openai, deepseek)')
  .option('-m, --model <name>', 'Model name')
  .option('--no-tui', 'Use simple REPL instead of TUI')
  .option('--server <url>', 'Backend server URL for LLM requests')
  .parse(process.argv);

const opts = program.opts();

// ---- Backend communication ----

async function sendToBackend(text: string): Promise<void> {
  const serverUrl = opts.server || process.env.ASD_SERVER_URL || 'http://localhost:9020';
  try {
    const response = await fetch(`${serverUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    // Non-streaming fallback — response is returned as a single chunk
    const data = await response.json();
    if (data.content) {
      // The content is returned all at once
      // We split it into chunks for typewriter effect simulation
      const words = data.content.split(/(\s+)/);
      for (const word of words) {
        await new Promise(r => setTimeout(r, 15));
        // Chunks are handled by the onUserInput promise resolution
      }
      return data.content;
    }
  } catch {
    // If backend is unavailable, show a helpful message
    const msg = 'Backend server unavailable. Start the Python backend with:\n' +
                '  python -m ascend_agent.tools.server\n' +
                'Or set --server to your server URL.';
    throw new Error(msg);
  }
}

// ---- Simulated streaming for demo/testing ----

async function* simulateStream(text: string): AsyncGenerator<string> {
  const words = text.split(/(?<=\s)/g);
  for (const word of words) {
    await new Promise(r => setTimeout(r, 20 + Math.random() * 30));
    yield word;
  }
}

// ---- Main ----

async function handleUserInput(text: string): Promise<void> {
  try {
    // Try to connect to the Python backend for real streaming
    const serverUrl = opts.server || process.env.ASD_SERVER_URL || 'http://localhost:9020';

    const response = await fetch(`${serverUrl}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (!data || data === '[DONE]') continue;
          try {
            const parsed = JSON.parse(data);
            const content = parsed?.choices?.[0]?.delta?.content ?? '';
            // Content is handled by the TUI's streaming hook
            // but since onUserInput is a single promise, we need
            // to integrate differently. For now, just log.
          } catch {
            // Non-JSON chunk
          }
        }
      }
    }
  } catch {
    // Backend unavailable — show demo message
    // (In production, the TUI shows this as a system message)
    console.error('Backend unavailable. Set --server or start the Python server.');
  }
}

// Launch the TUI
if (opts.noTui || !isTerminal()) {
  // Simple non-TUI mode
  console.log('Launching in simple REPL mode. Use `asd` without --no-tui for the TUI.');
  // Fall back to Python REPL
  process.exit(0);
} else {
  const provider = opts.provider || resolveProvider();
  const model = opts.model || resolveModel();

  const { waitUntilExit } = render(
    React.createElement(App, {
      provider,
      model,
      onUserInput: handleUserInput,
      onQuit: () => process.exit(0),
    }),
  );

  // waitUntilExit() is handled by Ink automatically
}
